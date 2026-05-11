from flask import Flask, request, jsonify, render_template
import math
import re

app = Flask(__name__)

# Allowed token pattern for expression validation
_VALID_EXPR = re.compile(
    r'^[\d+\-*/().%\s^!]|'
    r'(math\.(sin|cos|tan|log10?|log|sqrt|factorial|fabs)|abs|round|pi|e)'
)

def safe_calculate(expression):
    """Safely evaluate arithmetic expressions with scientific functions."""
    expression = expression.strip()

    # Replace scientific function names BEFORE validation
    expression = expression.replace('sqrt(', 'math.sqrt(')
    expression = expression.replace('sin(', 'math.sin(')
    expression = expression.replace('cos(', 'math.cos(')
    expression = expression.replace('tan(', 'math.tan(')
    expression = expression.replace('log(', 'math.log10(')
    expression = expression.replace('ln(', 'math.log(')
    expression = expression.replace('abs(', 'math.fabs(')
    expression = expression.replace('^', '**')
    expression = expression.replace('pi', str(math.pi))
    expression = expression.replace('e', str(math.e))

    # Handle factorial: e.g. 5! → math.factorial(5)
    expression = re.sub(r'(\d+)!', lambda m: f'math.factorial({m.group(1)})', expression)

    # Validate: only digits, operators, parens, dots, spaces, and math.* calls
    if not re.match(r'^[\d+\-*/().\s**]+$',
                    re.sub(r'math\.(sin|cos|tan|log10|log|sqrt|factorial|fabs)\b', '', expression)):
        raise ValueError("Invalid characters in expression")

    safe_dict = {"__builtins__": {}, "math": math}
    result = eval(expression, safe_dict)  # nosec

    if isinstance(result, float) and result.is_integer():
        return int(result)
    if isinstance(result, float):
        return round(result, 10)
    return result


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.get_json()
    expression = data.get('expression', '').strip()

    if not expression:
        return jsonify({'error': 'No expression provided'}), 400

    try:
        result = safe_calculate(expression)
        return jsonify({'result': result, 'expression': expression})
    except ZeroDivisionError:
        return jsonify({'error': 'Division by zero'}), 400
    except Exception as e:
        return jsonify({'error': f'Invalid expression: {str(e)}'}), 400


@app.route('/voice', methods=['POST'])
def voice_parse():
    """Parse a voice transcript into a math expression."""
    data = request.get_json()
    transcript = data.get('transcript', '').lower().strip()

    replacements = [
        # Multi-word phrases first (longest first)
        ('multiplied by', '*'), ('divided by', '/'), ('added to', '+'),
        ('take away', '-'), ('to the power of', '^'), ('to the power', '^'),
        ('square root of', 'sqrt('), ('square root', 'sqrt('),
        ('natural log of', 'ln('), ('natural log', 'ln('),
        ('logarithm of', 'log('), ('absolute value of', 'abs('),
        ('sine of', 'sin('), ('cosine of', 'cos('), ('tangent of', 'tan('),
        # Single-word functions
        ('squared', '^2'), ('cubed', '^3'),
        ('sine', 'sin('), ('cosine', 'cos('), ('tangent', 'tan('),
        ('sin', 'sin('), ('cos', 'cos('), ('tan', 'tan('),
        ('logarithm', 'log('), ('log', 'log('), ('ln', 'ln('),
        ('sqrt', 'sqrt('), ('root', 'sqrt('), ('abs', 'abs('),
        # Numbers
        ('zero', '0'), ('one', '1'), ('two', '2'), ('three', '3'), ('four', '4'),
        ('five', '5'), ('six', '6'), ('seven', '7'), ('eight', '8'), ('nine', '9'),
        ('ten', '10'), ('eleven', '11'), ('twelve', '12'), ('thirteen', '13'),
        ('fourteen', '14'), ('fifteen', '15'), ('sixteen', '16'), ('seventeen', '17'),
        ('eighteen', '18'), ('nineteen', '19'), ('twenty', '20'), ('thirty', '30'),
        ('forty', '40'), ('fifty', '50'), ('sixty', '60'), ('seventy', '70'),
        ('eighty', '80'), ('ninety', '90'), ('hundred', '*100'),
        # Operators
        ('plus', '+'), ('add', '+'), ('and', '+'),
        ('minus', '-'), ('subtract', '-'),
        ('times', '*'), ('multiply', '*'),
        ('divide', '/'), ('over', '/'),
        # Misc
        ('percent', '/100'), ('point', '.'),
        ('equals', ''), ('equal', ''), ('calculate', ''), ('what is', ''), ('compute', ''),
        ('pi', 'pi'), ('pie', 'pi'),
        ('of', ''),
    ]

    expr = transcript
    for word, symbol in replacements:
        expr = re.sub(r'\b' + re.escape(word) + r'\b', symbol, expr)

    # Auto-close parentheses
    expr += ')' * max(0, expr.count('(') - expr.count(')'))

    # Strip whitespace and characters not valid in expressions
    expr = re.sub(r'\s+', '', expr)
    expr = re.sub(r'[^0-9+\-*/.()%^!sincotaglbqrpie]', '', expr)

    if not expr:
        return jsonify({'error': 'Could not parse voice input', 'transcript': transcript}), 400

    try:
        result = safe_calculate(expr)
        return jsonify({'expression': expr, 'result': result, 'transcript': transcript})
    except Exception as e:
        return jsonify({
            'error': f'Could not calculate: {str(e)}',
            'expression': expr,
            'transcript': transcript
        }), 400


if __name__ == '__main__':
    app.run(debug=True, port=5000)
