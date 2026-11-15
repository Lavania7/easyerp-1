"""Bounded decimal/rational formulas for the calculation workspace."""
from fractions import Fraction
import re


class FormulaError(ValueError):
    pass


def fail(code):
    raise FormulaError(code)


def normalize(expression):
    if not isinstance(expression, str):
        fail("syntax")
    source = expression.strip()
    if not source:
        fail("empty")
    if len(source) > 512:
        fail("limit")
    source = re.sub(r"\\(?:left|right)\b", "", source)
    source = re.sub(r"\\(?:cdot|times)\b", "*", source)
    source = re.sub(r"\\div\b", "/", source)
    source = re.sub(r"\\(?:mathrm|operatorname)\{([A-Za-z]+)\}", r"\1", source)
    source = re.sub(r"_\{([A-Za-z0-9]+)\}", r"_\1", source)
    source = re.sub(r"\\(eta|alpha|beta|gamma|theta)\b", r"\1", source)
    source = re.sub(r"\\(max|min)\b", r"\1", source)
    source = re.sub(r"\\[,;!]", "", source)
    source = source.translate(str.maketrans({"×": "*", "÷": "/", ":": "/", "−": "-", "η": "eta"}))
    source = source.replace(",", ";" if re.search(r"\b(?:max|min)\s*\(", source) else ".")
    position = 0

    def group(depth):
        nonlocal position
        if depth > 32:
            fail("limit")
        output = ""
        while position < len(source) and source[position] != "}":
            if source.startswith(r"\frac", position):
                position += 5
                parts = []
                for _ in range(2):
                    while position < len(source) and source[position].isspace():
                        position += 1
                    if position >= len(source) or source[position] != "{":
                        fail("syntax")
                    position += 1
                    parts.append(group(depth + 1))
                    if position >= len(source) or source[position] != "}":
                        fail("syntax")
                    position += 1
                output += "((" + parts[0] + ")/(" + parts[1] + "))"
            elif source[position] == "{":
                position += 1
                output += "(" + group(depth + 1) + ")"
                if position >= len(source) or source[position] != "}":
                    fail("syntax")
                position += 1
            else:
                output += source[position]
                position += 1
        return output

    normalized = group(0)
    if position != len(source):
        fail("syntax")
    assignment = normalized.split("=")
    if len(assignment) > 2 or len(assignment) == 2 and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*\s*", assignment[0]):
        fail("syntax")
    result = assignment[-1].strip()
    if re.search(r"[^A-Za-z0-9_\s.+*/()^;\-]", result):
        fail("syntax")
    return result


def parameters(expression):
    return list(dict.fromkeys(name for name in re.findall(r"[A-Za-z][A-Za-z0-9_]*", normalize(expression)) if name not in ("max", "min")))


def evaluate(expression, values=None):
    source = normalize(expression)
    values = values or {}
    position = 0

    def bounded(value):
        if len(str(abs(value.numerator))) > 768 or len(str(value.denominator)) > 768:
            fail("limit")
        return value

    def space():
        nonlocal position
        while position < len(source) and source[position].isspace():
            position += 1

    def peek():
        return source[position:position + 1]

    def decimal(raw):
        if len(raw.replace(".", "").lstrip("+-")) > 120:
            fail("limit")
        return bounded(Fraction(raw))

    def atom(depth):
        nonlocal position
        if depth > 32:
            fail("limit")
        space()
        if peek() == "(":
            position += 1
            value = sum_value(depth + 1)
            space()
            if peek() != ")":
                fail("syntax")
            position += 1
            return value
        name = re.match(r"[A-Za-z][A-Za-z0-9_]*", source[position:])
        if name:
            name = name[0]
            position += len(name)
            if name in ("max", "min"):
                space()
                if peek() != "(":
                    fail("syntax")
                position += 1
                args = [sum_value(depth + 1)]
                space()
                while peek() == ";":
                    position += 1
                    args.append(sum_value(depth + 1))
                    space()
                if peek() != ")" or len(args) < 2:
                    fail("syntax")
                position += 1
                return (max if name == "max" else min)(args)
            raw = values.get(name)
            if not isinstance(raw, str) or not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", raw.strip().replace(",", ".")):
                fail("parameter")
            return decimal(raw.strip().replace(",", "."))
        match = re.match(r"(?:\d+(?:\.\d*)?|\.\d+)", source[position:])
        if not match:
            fail("syntax")
        position += len(match[0])
        return decimal(match[0])

    def power(depth):
        nonlocal position
        left = atom(depth)
        space()
        if peek() == "^":
            position += 1
            right = unary(depth + 1)
            if right.denominator != 1 or abs(right.numerator) > 100:
                fail("exponent")
            if not left and right < 0:
                fail("division")
            exponent = right.numerator
            if max(len(str(abs(left.numerator))), len(str(left.denominator))) * abs(exponent) > 4000:
                fail("limit")
            left = bounded(left ** exponent)
        return left

    def unary(depth):
        nonlocal position
        if depth > 32:
            fail("limit")
        space()
        if peek() in ("+", "-"):
            sign = peek()
            position += 1
            value = unary(depth + 1)
            return -value if sign == "-" else value
        return power(depth)

    def product(depth):
        nonlocal position
        left = unary(depth)
        while True:
            space()
            operator = peek()
            if operator in ("*", "/"):
                position += 1
            elif operator and re.match(r"[A-Za-z(]", operator):
                operator = "*"
            else:
                return left
            right = unary(depth)
            if operator == "/" and not right:
                fail("division")
            left = bounded(left * right if operator == "*" else left / right)

    def sum_value(depth):
        nonlocal position
        left = product(depth)
        while True:
            space()
            operator = peek()
            if operator not in ("+", "-"):
                return left
            position += 1
            right = product(depth)
            left = bounded(left + right if operator == "+" else left - right)

    result = sum_value(0)
    space()
    if position != len(source):
        fail("syntax")
    numerator, denominator = abs(result.numerator), result.denominator
    scaled, remainder = divmod(numerator * 10 ** 20, denominator)
    exact = remainder == 0
    if remainder * 2 >= denominator:
        scaled += 1
    integer, decimals = divmod(scaled, 10 ** 20)
    tail = str(decimals).zfill(20).rstrip("0")
    value = ("-" if result < 0 and scaled else "") + str(integer) + ("." + tail if tail else "")
    return {"value": value, "exact": exact}
