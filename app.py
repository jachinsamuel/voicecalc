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


def parse_voice_transcript(transcript):
    """Enhanced NLP parser for mathematical expressions."""
    transcript = transcript.lower().strip()
    
    # Stage 1: Normalize homophones and common speech patterns
    transcript = re.sub(r'\bfor\b', 'four', transcript)
    transcript = re.sub(r'\bto\b', 'too', transcript)
    
    # Stage 2: Handle compound numbers (twenty three → 23, one hundred twenty five → 125)
    def expand_numbers(text):
        """Convert word numbers to digits, handling compound numbers."""
        ones = {
            'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
            'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
            'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
            'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
            'eighteen': '18', 'nineteen': '19'
        }
        tens = {
            'twenty': '20', 'thirty': '30', 'forty': '40', 'fifty': '50',
            'sixty': '60', 'seventy': '70', 'eighty': '80', 'ninety': '90'
        }
        
        # Handle "X hundred Y" pattern (e.g., "one hundred twenty three" → 123)
        pattern = r'\b(' + '|'.join(ones.keys()) + r')\s+hundred\s+(' + '|'.join(tens.keys()) + r')\s+(' + '|'.join(ones.keys()) + r')\b'
        def replace_hundred_tens_ones(m):
            num = int(ones[m.group(1)]) * 100
            num += int(tens[m.group(2)])
            num += int(ones[m.group(3)])
            return str(num)
        text = re.sub(pattern, replace_hundred_tens_ones, text)
        
        # Handle "X hundred Y" where Y is a tens value (e.g., "one hundred twenty")
        pattern2 = r'\b(' + '|'.join(ones.keys()) + r')\s+hundred\s+(' + '|'.join(tens.keys()) + r')\b'
        def replace_hundred_tens(m):
            num = int(ones[m.group(1)]) * 100
            num += int(tens[m.group(2)])
            return str(num)
        text = re.sub(pattern2, replace_hundred_tens, text)
        
        # Replace "N hundred" where N is a number word
        text = re.sub(r'\b(' + '|'.join(list(ones.keys())[:10]) + r')\s+hundred\b', 
                     lambda m: str(int(ones[m.group(1)]) * 100), text)
        
        # Handle "twenty three" → "23" pattern
        pattern3 = r'\b(' + '|'.join(tens.keys()) + r')\s+(' + '|'.join(ones.keys()) + r')\b'
        def combine_tens_ones(m):
            tens_val = int(tens[m.group(1)])
            ones_val = int(ones[m.group(2)])
            return str(tens_val + ones_val)
        text = re.sub(pattern3, combine_tens_ones, text)
        
        # Replace remaining number words
        for word, val in list(ones.items()) + list(tens.items()):
            text = re.sub(r'\b' + word + r'\b', val, text)
        
        return text
    
    transcript = expand_numbers(transcript)
    
    # Stage 3: Handle function-of patterns
    function_patterns = {
        r'sine\s+of\s+': 'sin(',
        r'cosine\s+of\s+': 'cos(',
        r'tangent\s+of\s+': 'tan(',
        r'sin\s+of\s+': 'sin(',
        r'cos\s+of\s+': 'cos(',
        r'tan\s+of\s+': 'tan(',
        r'square\s+root\s+of\s+': 'sqrt(',
        r'sqrt\s+of\s+': 'sqrt(',
        r'natural\s+log\s+of\s+': 'ln(',
        r'logarithm\s+of\s+': 'log(',
        r'log\s+of\s+': 'log(',
        r'absolute\s+value\s+of\s+': 'abs(',
        r'abs\s+of\s+': 'abs(',
    }
    
    for pattern, replacement in function_patterns.items():
        transcript = re.sub(pattern, replacement, transcript)
    
    # Stage 4: Replace multi-word operations (before single words)
    operations = [
        ('multiplied by', '*'),
        ('divided by', '/'),
        ('added to', '+'),
        ('take away', '-'),
        ('to the power of', '^'),
        ('to the power', '^'),
        ('percent of', '*0.01*'),
    ]
    
    for phrase, op in operations:
        transcript = re.sub(r'\b' + re.escape(phrase) + r'\b', ' ' + op + ' ', transcript)
    
    # Stage 5: Handle single-word operations
    single_ops = [
        ('squared', '^2'),
        ('cubed', '^3'),
        ('factorial', '!'),
        ('percent', '*0.01'),
        ('point', '.'),
        ('plus', '+'),
        ('add', '+'),
        ('minus', '-'),
        ('subtract', '-'),
        ('times', '*'),
        ('multiply', '*'),
        ('divide', '/'),
        ('over', '/'),
        ('modulo', '%'),
        ('mod', '%'),
        ('remainder', '%'),
    ]
    
    for word, op in single_ops:
        transcript = re.sub(r'\b' + word + r'\b', op, transcript)
    
    # Stage 6: Handle function names without "of"
    functions = [
        ('sine', 'sin('),
        ('cosine', 'cos('),
        ('tangent', 'tan('),
        ('sin', 'sin('),
        ('cos', 'cos('),
        ('tan', 'tan('),
        ('logarithm', 'log('),
        ('log', 'log('),
        ('ln', 'ln('),
        ('sqrt', 'sqrt('),
        ('root', 'sqrt('),
        ('abs', 'abs('),
    ]
    
    for func_name, func_call in functions:
        transcript = re.sub(r'\b' + func_name + r'\b', func_call, transcript)
    
    # Stage 7: Handle constants and special words
    constants = [
        ('pie', 'pi'),
        ('pi', 'pi'),
        ('e', 'e'),
    ]
    
    for word, const in constants:
        transcript = re.sub(r'\b' + word + r'\b', const, transcript)
    
    # Stage 8: Remove filler words
    fillers = [
        'equals', 'equal', 'calculate', 'what is', 'compute',
        'please', 'is', 'the',
    ]
    
    for filler in fillers:
        transcript = re.sub(r'\b' + filler + r'\b', '', transcript)
    
    # Stage 9: Clean up the expression
    expr = transcript
    expr = re.sub(r'\s+', '', expr)
    
    # Stage 10: Smart parenthesis handling
    # Count parentheses for functions and add missing closing parens
    open_parens = expr.count('(')
    close_parens = expr.count(')')
    expr += ')' * max(0, open_parens - close_parens)
    
    # Stage 11: Remove invalid characters
    expr = re.sub(r'[^0-9+\-*/.()%^!sincotaglbqrpie]', '', expr)
    
    return expr


@app.route('/voice', methods=['POST'])
def voice_parse():
    """Parse a voice transcript into a math expression."""
    data = request.get_json()
    transcript = data.get('transcript', '').lower().strip()

    if not transcript:
        return jsonify({'error': 'No transcript provided'}), 400

    expr = parse_voice_transcript(transcript)

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
