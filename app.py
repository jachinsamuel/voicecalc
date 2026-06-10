import ast
import math
import re
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Allowed functions and constants from the math module
MATH_FUNCS = {
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'log': math.log10,
    'log10': math.log10,
    'ln': math.log,
    'sqrt': math.sqrt,
    'factorial': math.factorial,
    'abs': math.fabs,
    'fabs': math.fabs
}

MATH_CONSTANTS = {
    'pi': math.pi,
    'e': math.e
}

class SafeEvaluator(ast.NodeVisitor):
    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return left / right
        elif isinstance(node.op, ast.Pow):
            if right > 100 or left > 10000:  # Prevent huge numbers from crashing the server
                raise ValueError("Exponent or base too large")
            return left ** right
        elif isinstance(node.op, ast.Mod):
            return left % right
        raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        
    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        elif isinstance(node.op, ast.USub):
            return -operand
        raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        
    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed")
        func_name = node.func.id
        if func_name not in MATH_FUNCS:
            raise ValueError(f"Unsupported function: {func_name}")
        args = [self.visit(arg) for arg in node.args]
        return MATH_FUNCS[func_name](*args)
        
    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric constants are allowed")
        
    def visit_Name(self, node):
        if node.id in MATH_CONSTANTS:
            return MATH_CONSTANTS[node.id]
        raise ValueError(f"Unsupported variable: {node.id}")
        
    def visit_Expr(self, node):
        return self.visit(node.value)
        
    def generic_visit(self, node):
        raise ValueError(f"Unsupported expression construct: {type(node).__name__}")

def safe_calculate(expression):
    """Safely evaluate arithmetic expressions using an AST."""
    expression = expression.strip()
    if not expression:
        raise ValueError("Empty expression")

    # Replace specific symbols for python syntax
    expression = expression.replace('^', '**')
    # Handle factorial (e.g., 5! -> factorial(5))
    expression = re.sub(r'(\d+(?:\.\d+)?)!', r'factorial(\1)', expression)

    try:
        tree = ast.parse(expression, mode='eval')
        evaluator = SafeEvaluator()
        result = evaluator.visit(tree.body)
        
        if isinstance(result, float) and result.is_integer():
            return int(result)
        if isinstance(result, float):
            return round(result, 10)
        return result
    except SyntaxError:
        raise ValueError("Invalid syntax")
    except ZeroDivisionError:
        raise
    except Exception as e:
        raise ValueError(str(e))


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
