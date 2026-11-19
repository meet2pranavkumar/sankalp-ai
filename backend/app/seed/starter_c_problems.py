"""Practice problems that go with the starter course.

Each problem has a reference solution in C. tests/test_seed.py compiles it and checks that
it passes every test case, so a wrong expected answer cannot slip in.
Tests are (input, expected_output, is_hidden). The first test of each problem is a visible sample.
"""

PROBLEMS = [
    {
        "title": "Hello Sankalp",
        "difficulty": "easy",
        "tags": ["basics", "output"],
        "statement_md": """## Task

Print exactly this line:

```
Hello, Sankalp!
```

## Input

There is no input.

## Output

Print `Hello, Sankalp!` followed by a new line.
""",
        "tests": [("", "Hello, Sankalp!\n", False)],
        "reference": r"""
#include <stdio.h>
int main(void) { printf("Hello, Sankalp!\n"); return 0; }
""",
    },
    {
        "title": "Sum of Two Numbers",
        "difficulty": "easy",
        "tags": ["basics", "input"],
        "statement_md": """## Task

Read two integers and print their sum.

## Input

Two integers `a` and `b` on one line, separated by a space. Each is between -1000000 and 1000000.

## Output

One integer: `a + b`.

## Example

Input:
```
12 30
```
Output:
```
42
```
""",
        "tests": [
            ("12 30\n", "42\n", False),
            ("-5 5\n", "0\n", True),
            ("0 0\n", "0\n", True),
            ("1000000 1000000\n", "2000000\n", True),
            ("-7 -8\n", "-15\n", True),
        ],
        "reference": r"""
#include <stdio.h>
int main(void) { int a, b; scanf("%d %d", &a, &b); printf("%d\n", a + b); return 0; }
""",
    },
    {
        "title": "Area of a Rectangle",
        "difficulty": "easy",
        "tags": ["basics", "input", "arithmetic"],
        "statement_md": """## Task

Read the length and width of a rectangle and print its area.

## Input

Two integers `length` and `width` (1 to 10000), separated by a space.

## Output

One integer: the area.

## Example

Input:
```
6 4
```
Output:
```
24
```
""",
        "tests": [
            ("6 4\n", "24\n", False),
            ("1 1\n", "1\n", True),
            ("10000 10000\n", "100000000\n", True),
            ("7 3\n", "21\n", True),
        ],
        "reference": r"""
#include <stdio.h>
int main(void) { int l, w; scanf("%d %d", &l, &w); printf("%d\n", l * w); return 0; }
""",
    },
    {
        "title": "Average of Three Numbers",
        "difficulty": "easy",
        "tags": ["arithmetic", "input"],
        "statement_md": """## Task

Read three integers and print their average with exactly 2 digits after the decimal point.

## Input

Three integers separated by spaces, each between -1000 and 1000.

## Output

The average, printed with 2 digits after the decimal point.

## Example

Input:
```
10 20 25
```
Output:
```
18.33
```

**Hint:** dividing two `int` values in C throws away the decimal part. Use `3.0` or a cast.
""",
        "tests": [
            ("10 20 25\n", "18.33\n", False),
            ("10 20 30\n", "20.00\n", True),
            ("1 2 2\n", "1.67\n", True),
            ("0 0 1\n", "0.33\n", True),
            ("-3 3 10\n", "3.33\n", True),
            ("-1000 -1000 -1000\n", "-1000.00\n", True),
        ],
        "reference": r"""
#include <stdio.h>
int main(void) { int a, b, c; scanf("%d %d %d", &a, &b, &c); printf("%.2f\n", (a + b + c) / 3.0); return 0; }
""",
    },
    {
        "title": "Even or Odd",
        "difficulty": "easy",
        "tags": ["conditions", "arithmetic"],
        "statement_md": """## Task

Read an integer. Print `Even` if it is even and `Odd` if it is odd.

## Input

One integer `n` between -1000000 and 1000000.

## Output

`Even` or `Odd`.

## Example

Input:
```
7
```
Output:
```
Odd
```
""",
        "tests": [
            ("7\n", "Odd\n", False),
            ("10\n", "Even\n", True),
            ("0\n", "Even\n", True),
            ("-3\n", "Odd\n", True),
            ("-8\n", "Even\n", True),
            ("999999\n", "Odd\n", True),
        ],
        "reference": r"""
#include <stdio.h>
int main(void) { int n; scanf("%d", &n); printf(n % 2 == 0 ? "Even\n" : "Odd\n"); return 0; }
""",
    },
    {
        "title": "Largest of Three",
        "difficulty": "easy",
        "tags": ["conditions"],
        "statement_md": """## Task

Read three integers and print the largest one.

## Input

Three integers separated by spaces, each between -1000000 and 1000000.

## Output

The largest of the three.

## Example

Input:
```
4 17 9
```
Output:
```
17
```
""",
        "tests": [
            ("4 17 9\n", "17\n", False),
            ("5 5 5\n", "5\n", True),
            ("-1 -2 -3\n", "-1\n", True),
            ("100 20 3\n", "100\n", True),
            ("1 2 3\n", "3\n", True),
            ("-5 0 -5\n", "0\n", True),
        ],
        "reference": r"""
#include <stdio.h>
int main(void) { int a, b, c; scanf("%d %d %d", &a, &b, &c);
  int m = a; if (b > m) m = b; if (c > m) m = c; printf("%d\n", m); return 0; }
""",
    },
    {
        "title": "Grade Calculator",
        "difficulty": "easy",
        "tags": ["conditions"],
        "statement_md": """## Task

Read a student's marks and print the grade:

| Marks | Grade |
|---|---|
| 80 to 100 | A |
| 60 to 79 | B |
| 40 to 59 | C |
| 0 to 39 | F |

## Input

One integer between 0 and 100.

## Output

One letter: `A`, `B`, `C` or `F`.

## Example

Input:
```
65
```
Output:
```
B
```
""",
        "tests": [
            ("65\n", "B\n", False),
            ("100\n", "A\n", True),
            ("80\n", "A\n", True),
            ("79\n", "B\n", True),
            ("60\n", "B\n", True),
            ("59\n", "C\n", True),
            ("40\n", "C\n", True),
            ("39\n", "F\n", True),
            ("0\n", "F\n", True),
        ],
        "reference": r"""
#include <stdio.h>
int main(void) { int m; scanf("%d", &m);
  if (m >= 80) printf("A\n"); else if (m >= 60) printf("B\n"); else if (m >= 40) printf("C\n"); else printf("F\n");
  return 0; }
""",
    },
    {
        "title": "Sum from 1 to N",
        "difficulty": "easy",
        "tags": ["loops"],
        "statement_md": """## Task

Read `n` and print the sum `1 + 2 + 3 + ... + n`.

## Input

One integer `n` between 1 and 10000.

## Output

The sum.

## Example

Input:
```
5
```
Output:
```
15
```
""",
        "tests": [
            ("5\n", "15\n", False),
            ("1\n", "1\n", True),
            ("100\n", "5050\n", True),
            ("10000\n", "50005000\n", True),
            ("37\n", "703\n", True),
        ],
        "reference": r"""
#include <stdio.h>
int main(void) { int n, s = 0; scanf("%d", &n); for (int i = 1; i <= n; i++) s += i; printf("%d\n", s); return 0; }
""",
    },
    {
        "title": "Multiplication Table",
        "difficulty": "easy",
        "tags": ["loops", "output"],
        "statement_md": """## Task

Read `n` and print its multiplication table from 1 to 10.

## Input

One integer `n` between 1 and 100.

## Output

Ten lines. Line `i` is written exactly like this: `n x i = result`

## Example

Input:
```
3
```
Output (first 3 lines of 10):
```
3 x 1 = 3
3 x 2 = 6
3 x 3 = 9
```
""",
        "tests": [
            ("3\n", "".join(f"3 x {i} = {3 * i}\n" for i in range(1, 11)), False),
            ("1\n", "".join(f"1 x {i} = {i}\n" for i in range(1, 11)), True),
            ("12\n", "".join(f"12 x {i} = {12 * i}\n" for i in range(1, 11)), True),
            ("100\n", "".join(f"100 x {i} = {100 * i}\n" for i in range(1, 11)), True),
        ],
        "reference": r"""
#include <stdio.h>
int main(void) { int n; scanf("%d", &n); for (int i = 1; i <= 10; i++) printf("%d x %d = %d\n", n, i, n * i); return 0; }
""",
    },
    {
        "title": "Factorial",
        "difficulty": "easy",
        "tags": ["loops", "functions"],
        "statement_md": """## Task

Read `n` and print `n!` (n factorial). The factorial is `1 x 2 x 3 x ... x n`. By definition `0! = 1`.

## Input

One integer `n` between 0 and 12.

## Output

The value of `n!`.

## Example

Input:
```
5
```
Output:
```
120
```
""",
        "tests": [
            ("5\n", "120\n", False),
            ("0\n", "1\n", True),
            ("1\n", "1\n", True),
            ("10\n", "3628800\n", True),
            ("12\n", "479001600\n", True),
            ("7\n", "5040\n", True),
        ],
        "reference": r"""
#include <stdio.h>
int main(void) { int n; long long f = 1; scanf("%d", &n); for (int i = 2; i <= n; i++) f *= i; printf("%lld\n", f); return 0; }
""",
    },
    {
        "title": "Count Digits",
        "difficulty": "easy",
        "tags": ["loops", "arithmetic"],
        "statement_md": """## Task

Read a non-negative integer and print how many digits it has. The number `0` has 1 digit.

## Input

One integer `n` between 0 and 1000000000.

## Output

The number of digits.

## Example

Input:
```
90210
```
Output:
```
5
```
""",
        "tests": [
            ("90210\n", "5\n", False),
            ("0\n", "1\n", True),
            ("7\n", "1\n", True),
            ("10\n", "2\n", True),
            ("999999999\n", "9\n", True),
            ("1000000000\n", "10\n", True),
        ],
        "reference": r"""
#include <stdio.h>
int main(void) { long long n; int d = 0; scanf("%lld", &n); if (n == 0) d = 1; while (n > 0) { d++; n /= 10; } printf("%d\n", d); return 0; }
""",
    },
    {
        "title": "Triangle Pattern",
        "difficulty": "easy",
        "tags": ["loops", "patterns"],
        "statement_md": """## Task

Read `n` and print a triangle of `*` with `n` rows. Row `i` has `i` stars.

## Input

One integer `n` between 1 and 30.

## Output

`n` lines. Do not print spaces.

## Example

Input:
```
4
```
Output:
```
*
**
***
****
```
""",
        "tests": [
            ("4\n", "*\n**\n***\n****\n", False),
            ("1\n", "*\n", True),
            ("2\n", "*\n**\n", True),
            ("7\n", "".join("*" * i + "\n" for i in range(1, 8)), True),
            ("30\n", "".join("*" * i + "\n" for i in range(1, 31)), True),
        ],
        "reference": r"""
#include <stdio.h>
int main(void) { int n; scanf("%d", &n);
  for (int r = 1; r <= n; r++) { for (int c = 1; c <= r; c++) printf("*"); printf("\n"); } return 0; }
""",
    },
    {
        "title": "Reverse an Array",
        "difficulty": "easy",
        "tags": ["arrays"],
        "statement_md": """## Task

Read `n` numbers and print them in reverse order, separated by single spaces.

## Input

The first line has `n` (1 to 100). The second line has `n` integers.

## Output

The numbers in reverse order on one line, separated by a space. No space after the last number.

## Example

Input:
```
4
1 2 3 4
```
Output:
```
4 3 2 1
```
""",
        "tests": [
            ("4\n1 2 3 4\n", "4 3 2 1\n", False),
            ("1\n42\n", "42\n", True),
            ("5\n10 -20 30 -40 50\n", "50 -40 30 -20 10\n", True),
            ("2\n0 0\n", "0 0\n", True),
            ("6\n5 5 1 1 9 9\n", "9 9 1 1 5 5\n", True),
        ],
        "reference": r"""
#include <stdio.h>
int main(void) { int n, a[100]; scanf("%d", &n); for (int i = 0; i < n; i++) scanf("%d", &a[i]);
  for (int i = n - 1; i >= 0; i--) { printf("%d", a[i]); if (i > 0) printf(" "); } printf("\n"); return 0; }
""",
    },
    {
        "title": "Count Vowels",
        "difficulty": "easy",
        "tags": ["strings"],
        "statement_md": """## Task

Read one word and print how many vowels it has. The vowels are `a e i o u`, both small and capital letters.

## Input

One word of 1 to 99 English letters, without spaces.

## Output

The number of vowels.

## Example

Input:
```
Education
```
Output:
```
5
```
""",
        "tests": [
            ("Education\n", "5\n", False),
            ("rhythm\n", "0\n", True),
            ("AEIOU\n", "5\n", True),
            ("aeiou\n", "5\n", True),
            ("Programming\n", "3\n", True),
            ("x\n", "0\n", True),
        ],
        "reference": r"""
#include <stdio.h>
#include <ctype.h>
int main(void) { char w[100]; scanf("%s", w); int v = 0;
  for (int i = 0; w[i] != '\0'; i++) { char c = tolower(w[i]); if (c=='a'||c=='e'||c=='i'||c=='o'||c=='u') v++; }
  printf("%d\n", v); return 0; }
""",
    },
    {
        "title": "Prime Check",
        "difficulty": "medium",
        "tags": ["loops", "functions", "math"],
        "statement_md": """## Task

Read an integer and print `Prime` if it is a prime number, otherwise print `Not prime`.

A **prime** number is greater than 1 and can only be divided by 1 and itself. So 1 is **not** prime.

## Input

One integer `n` between 1 and 100000.

## Output

`Prime` or `Not prime`.

## Example

Input:
```
7
```
Output:
```
Prime
```
""",
        "tests": [
            ("7\n", "Prime\n", False),
            ("1\n", "Not prime\n", True),
            ("2\n", "Prime\n", True),
            ("4\n", "Not prime\n", True),
            ("97\n", "Prime\n", True),
            ("100\n", "Not prime\n", True),
            ("99991\n", "Prime\n", True),
            ("99999\n", "Not prime\n", True),
        ],
        "reference": r"""
#include <stdio.h>
int is_prime(int n) { if (n < 2) return 0; for (int i = 2; i * i <= n; i++) if (n % i == 0) return 0; return 1; }
int main(void) { int n; scanf("%d", &n); printf(is_prime(n) ? "Prime\n" : "Not prime\n"); return 0; }
""",
    },
]
