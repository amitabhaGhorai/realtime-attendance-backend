from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# 1. Health check
res = client.get('/api/health')
print('1. Health Check Status:', res.status_code, res.json())
assert res.status_code == 200

# 2. Login as Admin
login_res = client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
print('2. Admin Login Status:', login_res.status_code)
assert login_res.status_code == 200
token = login_res.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# 3. Get Me
me_res = client.get('/api/auth/me', headers=headers)
print('3. Me Profile:', me_res.status_code, me_res.json()['username'], me_res.json()['role'])
assert me_res.status_code == 200

# 4. List Students
stu_res = client.get('/api/students', headers=headers)
print('4. Students Count:', len(stu_res.json()))
assert len(stu_res.json()) >= 3

# 5. List Sessions
sess_res = client.get('/api/attendance/sessions', headers=headers)
sessions = sess_res.json()
print('5. Attendance Sessions Count:', len(sessions))
assert len(sessions) >= 1
active_session_id = sessions[0]['id']

# 6. PDF Export
pdf_res = client.get(f'/api/reports/export/pdf?session_id={active_session_id}', headers=headers)
print('6. PDF Export Status:', pdf_res.status_code, 'Content-Type:', pdf_res.headers.get('content-type'), 'Bytes:', len(pdf_res.content))
assert pdf_res.status_code == 200
assert b'%PDF' in pdf_res.content[:10]

# 7. CSV Export
csv_res = client.get(f'/api/reports/export/csv?session_id={active_session_id}', headers=headers)
print('7. CSV Export Status:', csv_res.status_code, 'Content-Type:', csv_res.headers.get('content-type'))
assert csv_res.status_code == 200
assert 'Roll No' in csv_res.text or 'Student Roll No' in csv_res.text

# 8. Check Frontend index.html served
fe_res = client.get('/')
print('8. Frontend Static Route Status:', fe_res.status_code, 'Has Root Div:', '<div id="root">' in fe_res.text)
assert fe_res.status_code == 200
assert '<div id="root">' in fe_res.text

print('\nALL INTEGRATION ENDPOINTS VERIFIED SUCCESSFULLY!')
