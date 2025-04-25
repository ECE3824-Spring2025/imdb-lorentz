from flask import Flask, request, render_template

app = Flask(__name__)

# Show login page
@app.route('/')
def index():
    return render_template('login.html')

# Show and process register form
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Save new user to text file
        with open('users.txt', 'a') as f:
            f.write(f"{username}:{password}\n")

        # Show popup and redirect to login
        return render_template('registered_popup.html', username=username)

    return render_template('register.html')

# Handle login form submission
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    try:
        with open('users.txt', 'r') as f:
            users = f.readlines()
            for user in users:
                saved_username, saved_password = user.strip().split(':')
                if username == saved_username and password == saved_password:
                    return render_template('welcome.html', username=username)
    except FileNotFoundError:
        pass

    # If no match found
    return render_template('login.html', error="Invalid username or password.")

if __name__ == '__main__':
    app.run(debug=True)
