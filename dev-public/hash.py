import hashlib
import secrets

data = secrets.token_hex(8)
data = "JuanForge est le meilleur dev"

print(f"{data!r} : {hashlib.sha256(data.encode()).hexdigest()}")