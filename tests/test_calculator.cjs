'use strict';
const assert = require('node:assert/strict');
const { evaluate, parameters } = require('../app/web/calculator.js');
const cases = [
  ['0.1 + 0.2', '0.3'],
  ['9007199254740993 + 0.0001', '9007199254740993.0001'],
  ['9999999999999999.9999 + .0001', '10000000000000000'],
  ['2+3*4', '14'],
  ['(2+3)*4', '20'],
  ['-(2 + 3) / -2', '2.5'],
  ['1--2', '3'],
  ['.5 + 1.', '1.5'],
  ['1,25 × 4 − 2 ÷ (1 + 1)', '4'],
  ['10/4/2', '1.25'],
  ['10-4-2', '4'],
  ['(1/3)*3', '1'],
  ['(1/7 + 2/7)*7', '3'],
  ['1/(2/(3/4))', '0.375'],
  ['-0', '0'],
  ['-0.000000000000000000001', '0', false],
  ['1/3', '0.33333333333333333333', false],
  ['2/3', '0.66666666666666666667', false],
  ['-2/3', '-0.66666666666666666667', false],
  ['0.999999999999999999999', '1', false],
  ['1/100000000000000000000', '0.00000000000000000001'],
];
for (const [expression, value, exact = true] of cases) assert.deepEqual(evaluate(expression), { value, exact }, expression);
const invalid = [
  ['', 'empty'], ['   ', 'empty'], ['1/0', 'division'], ['1/(2-2)', 'division'],
  ['0/0', 'division'], ['1+', 'syntax'], ['(1+2', 'syntax'], ['1+2)', 'syntax'],
  ['1 2', 'syntax'], ['1..2', 'syntax'], ['1,000.1', 'syntax'],
  ['1e3', 'parameter'], ['NaN', 'parameter'], ['Infinity', 'parameter'], ['2**3', 'syntax'],
  ['globalThis.hacked=1', 'syntax'], ['alert(1)', 'parameter'], ['constructor.constructor("return 1")()', 'syntax'],
  ['1;process.exit()', 'syntax'], ['<img src=x onerror=alert(1)>', 'syntax'],
  ['9'.repeat(121), 'limit'], ['1+'.repeat(257) + '1', 'limit'],
  ['('.repeat(34) + '1' + ')'.repeat(34), 'limit'], ['-'.repeat(35) + '1', 'limit'],
];
for (const [expression, code] of invalid) assert.throws(() => evaluate(expression), { message: code }, expression);
for (let number = -100; number <= 100; number++) {
  const sign = number < 0 ? '-' : '';
  const decimal = sign + Math.trunc(Math.abs(number) / 100) + '.' + String(Math.abs(number) % 100).padStart(2, '0');
  assert.equal(evaluate(`(${decimal}+0.01)*100`).value, String(number + 1));
  assert.equal(evaluate(`(${number}/7)*7`).value, String(number));
}
console.log(`PASS ${cases.length} valid cases, ${invalid.length} rejected cases, 402 decimal/rational invariants`);

const formulas = [
  [String.raw`\frac{q}{1-r}`, { q: '9', r: '0.1' }, '10'],
  [String.raw`A=\frac{a+\frac{b}{c}}{d}`, { a: '1', b: '1', c: '3', d: '4' }, '0.33333333333333333333'],
  ['a*(1+r)^n', { a: '100', r: '0.1', n: '2' }, '121'],
  [String.raw`2\cdot x+3\times y`, { x: '0.1', y: '0.2' }, '0.8'],
  [String.raw`\left(2+3\right)^{2}`, {}, '25'],
  ['2(3)', {}, '6'], ['-2^2', {}, '-4'], ['2^-2', {}, '0.25'],
  ['(1/7)*7', {}, '1'], ['2^3^2', {}, '512'],
];
for (const [expression, values, expected] of formulas) assert.equal(evaluate(expression, values).value, expected);
assert.deepEqual(parameters(String.raw`\frac{q}{1-r}`), ['q', 'r']);
assert.throws(() => evaluate('a', { a: '1+2' }), { message: 'parameter' });
assert.throws(() => evaluate('2^0.5'), { message: 'exponent' });
assert.throws(() => evaluate('2^101'), { message: 'exponent' });
assert.throws(() => evaluate('0^-1'), { message: 'division' });
assert.throws(() => evaluate(String.raw`\sqrt{4}`), { message: 'syntax' });
assert.throws(() => evaluate(String.raw`\frac{1}{}`), { message: 'syntax' });
assert.throws(() => evaluate(String.raw`\frac{1}{2`), { message: 'syntax' });
console.log('PASS safe LaTeX/parameters/powers and malformed-formula boundaries');
