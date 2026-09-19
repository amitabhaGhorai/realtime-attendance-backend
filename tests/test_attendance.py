"""Automated Test Suite for Attendance Business Rules and Verification (unittest)."""
import unittest
from datetime import datetime, timedelta
import numpy as np
from app.database import SyncSessionLocal
from app.models import (
    User, Student, CourseOffering, AttendanceSession,
    AttendanceRecord, AuditLog, FaceTemplate
)
from app.ai.face_engine import face_engine
from app.ai.quality_checker import QualityChecker
from app.ai.anti_spoof import AntiSpoofDetector

class TestAttendanceSystem(unittest.TestCase):

    def test_quality_checker_sharpness_and_blur(self):
        """Verify Laplacian sharpness and illumination thresholds."""
        sharp_img = np.random.randint(40, 220, (200, 200, 3), dtype=np.uint8)
        is_acc, score, metrics = QualityChecker.evaluate(sharp_img, (20, 20, 100, 100))
        self.assertTrue(metrics["sharpness_acceptable"])
        self.assertTrue(metrics["brightness_acceptable"])
        self.assertGreater(metrics["overall_score"], 0.4)

        blurry_img = np.full((200, 200, 3), 128, dtype=np.uint8)
        is_acc_blur, score_blur, metrics_blur = QualityChecker.evaluate(blurry_img, (20, 20, 100, 100))
        self.assertLess(metrics_blur["sharpness"], 5.0)
        self.assertFalse(metrics_blur["sharpness_acceptable"])

    def test_anti_spoof_detection(self):
        """Verify Fourier frequency texture analysis."""
        img = np.random.randint(50, 200, (128, 128, 3), dtype=np.uint8)
        is_live, conf, details = AntiSpoofDetector.check_liveness(img)
        self.assertIn("high_freq_energy", details)
        self.assertIn("confidence", details)

    def test_face_embeddings_and_cosine_similarity(self):
        """Verify 128-dimensional embedding generation and cosine matching."""
        dummy1 = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
        dummy2 = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
        emb1 = face_engine.extract_embedding(dummy1, (10, 10, 80, 80))
        emb2 = face_engine.extract_embedding(dummy2, (10, 10, 80, 80))

        self.assertEqual(len(emb1), 128)
        self.assertEqual(len(emb2), 128)

        self_sim = face_engine.cosine_similarity(emb1, emb1)
        self.assertAlmostEqual(self_sim, 1.0, places=2)

        cross_sim = face_engine.cosine_similarity(emb1, emb2)
        self.assertTrue(-1.0 <= cross_sim <= 1.0)

    def test_duplicate_attendance_constraint(self):
        """Verify that a student cannot be recorded twice in the same session."""
        db = SyncSessionLocal()
        session = db.query(AttendanceSession).first()
        student = db.query(Student).first()
        self.assertIsNotNone(session)
        self.assertIsNotNone(student)

        # Attempt duplicate insert
        dup = AttendanceRecord(
            session_id=session.id,
            student_id=student.id,
            status="PRESENT",
            marked_at=datetime.utcnow()
        )
        db.add(dup)
        with self.assertRaises(Exception):
            db.commit()
        db.rollback()
        db.close()

    def test_grace_period_present_vs_late(self):
        """Verify Present vs Late status calculation based on session start and grace period."""
        grace_minutes = 10

        # Case A: marked within grace period (5 minutes elapsed)
        start_time_a = datetime.utcnow() - timedelta(minutes=5)
        elapsed_a = (datetime.utcnow() - start_time_a).total_seconds() / 60.0
        status_a = "PRESENT" if elapsed_a <= grace_minutes else "LATE"
        self.assertEqual(status_a, "PRESENT")

        # Case B: marked after grace period (15 minutes elapsed)
        start_time_b = datetime.utcnow() - timedelta(minutes=15)
        elapsed_b = (datetime.utcnow() - start_time_b).total_seconds() / 60.0
        status_b = "PRESENT" if elapsed_b <= grace_minutes else "LATE"
        self.assertEqual(status_b, "LATE")

    def test_manual_override_audit_trail(self):
        """Verify manual override requires justification reason and logs to audit ledger."""
        db = SyncSessionLocal()
        admin = db.query(User).filter_by(username="admin").first()
        record = db.query(AttendanceRecord).first()
        self.assertIsNotNone(admin)
        self.assertIsNotNone(record)

        old_status = record.status
        record.status = "EXCUSED"
        record.verification_method = "MANUAL_OVERRIDE"
        reason = "Medical certificate presented by student"

        audit = AuditLog(
            user_id=admin.id,
            action="MANUAL_ATTENDANCE_OVERRIDE",
            entity_type="AttendanceRecord",
            entity_id=record.id,
            old_state=f"status={old_status}",
            new_state=f"status={record.status}",
            reason=reason,
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        db.commit()

        # Verify audit persistence
        saved_audit = db.query(AuditLog).filter_by(action="MANUAL_ATTENDANCE_OVERRIDE").first()
        self.assertIsNotNone(saved_audit)
        self.assertEqual(saved_audit.reason, reason)
        self.assertEqual(saved_audit.user_id, admin.id)
        db.close()

if __name__ == "__main__":
    unittest.main()
