import base64

class SimpleDB:
    def __init__(self):
        self.data = []

    def add_entry(self, username_encoded, password_encoded):
        self.data.append({
            'username': username_encoded,
            'password': password_encoded
        })

    def show_entries(self):
        for entry in self.data:
            print(entry)

def encode_and_store(db, username, password):
    username_bytes = username.encode('utf-8')
    password_bytes = password.encode('utf-8')

    username_encoded = base64.b64encode(username_bytes).decode('utf-8')
    password_encoded = base64.b64encode(password_bytes).decode('utf-8')

    db.add_entry(username_encoded, password_encoded)

def decode_base64(encoded_message):
    message_bytes = base64.b64decode(encoded_message)
    return message_bytes.decode('utf-8')

# Example Usage
def main():
    db = SimpleDB()
    encode_and_store(db, "testuser", "testpass")
    encode_and_store(db, "admin", "admin123")

    db.show_entries()

    # Decode example
    encoded_username = db.data[1]['password']
    print("Decoded username:", decode_base64(encoded_username))

if __name__ == "__main__":
    main()
