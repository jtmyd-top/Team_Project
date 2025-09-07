#{"accounts":{"76561199014129224":{"shared_secret":"qnY4tgYYg9/U30YqUuyjuKoxw/I=","identity_secret":"/OUBBxO+33UWgFKTTDYiKupuo14=","secret_1":"+txnplNO6g6eNA58rFCDjHsk8DU=","serial_number":"6313650064214493453","revocation_code":"R90288","account_name":"xxr1907454312","token_gid":"59a656a51e245ad","steamguard_scheme":2,"steamid":"76561199014129224","uri":"otpauth://totp/Steam:xxr1907454312?secret=VJ3DRNQGDCB57VG7IYVFF3FDXCVDDQ7S&issuer=Steam"}},"uuid_key":"android:ee37a61d-a6f7-4d86-83a4-7ed2d146ceff"}
import base64

shared_secret = 'g7xkfUtcNVd23C6KlxSfp7FmWxA='

print("Secret:", base64.b32encode(base64.b64dcode(shared_secret)).decode())