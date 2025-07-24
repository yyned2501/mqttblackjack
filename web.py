from flask import Flask, render_template

app = Flask(__name__, static_folder='statics')

@app.route('/')
def show_test():
    return render_template('blackjack.html')

if __name__ == '__main__':
    app.run(debug=True)