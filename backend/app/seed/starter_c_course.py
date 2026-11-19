"""The starter course: C Programming Basics. Written for diploma students who have never coded.

Rules for editing this file:
- Plain, short sentences. Every new word is explained when it first appears.
- A code block marked  ```c run  has a Run button. tests/test_seed.py compiles and runs every one of them.
- "Practice:" lines must name problems that exist in starter_c_problems.py.
"""

COURSE = {
    "title": "C Programming Basics",
    "description": (
        "Learn C from zero. Short lessons, code you can run and change right on the page, "
        "and practice problems for every topic. No setup needed."
    ),
    "language": "c",
    "units": [],
}

UNITS = COURSE["units"]

# ---------------------------------------------------------------- Unit 1
UNITS.append({
    "title": "1. Getting started",
    "lessons": [
        {
            "title": "Your first C program",
            "content_md": r"""
A **program** is a list of instructions for the computer. **C** is a language we use to write these instructions.
Here is the smallest useful C program. Press **Run** to see what it does.

```c run
#include <stdio.h>

int main(void) {
    printf("Hello, world!\n");
    return 0;
}
```

You can change the text inside the quotes and press **Run** again. Try it with your own name.

## What each line means

- `#include <stdio.h>` brings in the tools for printing and reading. `stdio` means *standard input and output*.
- `int main(void)` is where the program starts. Every C program has exactly one `main`.
- `{` and `}` mark the start and end of the instructions inside `main`.
- `printf("...")` prints text on the screen.
- `\n` means *go to a new line*. Without it, the next text stays on the same line.
- `return 0;` tells the computer that the program finished without problems.
- Every instruction ends with a **semicolon** `;`. Forgetting it is the most common mistake for beginners.

## Printing more than one line

```c run
#include <stdio.h>

int main(void) {
    printf("My name is Asha.\n");
    printf("I am learning C.\n");
    printf("This is fun!\n");
    return 0;
}
```

## Comments

A **comment** is a note for humans. The computer ignores it.

```c run
#include <stdio.h>

int main(void) {
    // This is a one-line comment
    /* This comment
       can use many lines */
    printf("Comments are ignored.\n");
    return 0;
}
```

## Remember

- Every program has `main`.
- Instructions end with `;`.
- Text goes inside double quotes `"..."`.

> **Practice:** Hello Sankalp
""",
        },
        {
            "title": "Compile, run and fix errors",
            "content_md": r"""
The computer does not understand C directly. A tool called a **compiler** changes your C text into machine code.
This is called **compiling**.

On this website you only press **Run**. We compile and run your code for you.

## On your own computer

If you have a compiler called `gcc`, you can do it yourself. Save your code in a file called `main.c`, then type:

```
gcc main.c -o main
./main
```

On Windows, run it with `main.exe` instead of `./main`.

## Errors are normal

Every programmer sees errors every day. An error message tells you **where** the problem is. Read it slowly.
It usually shows a line number, for example `main.c:5:`. Look at that line, and also at the line just before it.

Here are three common mistakes. These blocks do not have a Run button because they do not work.

**1. Missing semicolon**

```c
printf("Hello")
```

Fix: write `printf("Hello");`.

**2. Missing quotes**

```c
printf(Hello);
```

Fix: write `printf("Hello");`.

**3. Wrong spelling**

```c
Printf("Hello");
```

Fix: C cares about capital letters. Write `printf`, not `Printf`.

## Fix the program

The program below works. Break it on purpose: remove a semicolon, press **Run**, and read the error. Then fix it again.

```c run
#include <stdio.h>

int main(void) {
    printf("Errors help me learn.\n");
    return 0;
}
```

## Two kinds of problems

- A **compile error** means the compiler could not understand your code. Nothing runs.
- A **runtime error** means the program started but crashed. For example, it divided by zero.
- A **wrong answer** means the program ran fine but gave the wrong result. The computer cannot tell you about this. You must test.

> **Practice:** Hello Sankalp
""",
        },
    ],
})

# ---------------------------------------------------------------- Unit 2
UNITS.append({
    "title": "2. Data, input and output",
    "lessons": [
        {
            "title": "Variables and data types",
            "content_md": r"""
A **variable** is a named box in the computer's memory that holds a value. You choose the name and the type of value.

## The four basic types

| Type | Holds | Example |
|---|---|---|
| `int` | whole numbers | `17`, `-3`, `0` |
| `float` | numbers with a decimal point | `1.62` |
| `double` | decimal numbers, more exact than `float` | `3.14159265` |
| `char` | one single character | `'A'` |

Note: `char` values use **single** quotes `'A'`. Text in **double** quotes `"Hello"` is a different thing (a string, you will see it later).

```c run
#include <stdio.h>

int main(void) {
    int age = 17;
    float height = 1.62f;
    double pi = 3.14159265;
    char grade = 'A';

    printf("Age: %d\n", age);
    printf("Height: %.2f\n", height);
    printf("Pi: %.5f\n", pi);
    printf("Grade: %c\n", grade);
    return 0;
}
```

## Printing variables

`printf` uses a **format code** where the value should appear:

- `%d` for an `int`
- `%f` for a `float` or `double`. Write `%.2f` to show 2 digits after the point.
- `%c` for a `char`

The values come after the text, in the same order as the codes.

## Naming rules

- Use letters, digits and `_`. Do not start with a digit.
- Capital letters matter: `Age` and `age` are different.
- Pick clear names: `total_marks` is better than `x`.

## Changing a variable

```c run
#include <stdio.h>

int main(void) {
    int score = 10;
    printf("Score is %d\n", score);
    score = 25;
    printf("Score is now %d\n", score);
    return 0;
}
```

> **Practice:** Area of a Rectangle
""",
        },
        {
            "title": "Reading input with scanf",
            "content_md": r"""
So far our programs always give the same answer. With `scanf`, a program can read a value typed by the user.

```c run
#include <stdio.h>

int main(void) {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("Sum = %d\n", a + b);
    return 0;
}
```
```stdin
12 30
```

Below the code you can see an **Input** box. Whatever you type there is what `scanf` reads. Change the numbers and press **Run** again.

## How scanf works

- `"%d %d"` says: read two whole numbers.
- `&a` and `&b` tell `scanf` *where* to put the numbers. The `&` means "the address of the variable". For now, just remember to write it.
- Use the same format codes as `printf`: `%d` for `int`, `%f` for `float`, `%lf` for `double`.

## Reading a decimal number

```c run
#include <stdio.h>

int main(void) {
    float radius;
    scanf("%f", &radius);
    printf("Area of circle = %.2f\n", 3.14159f * radius * radius);
    return 0;
}
```
```stdin
2.5
```

## Important

- Input numbers can be separated by a space or a new line. `scanf` does not mind.
- In online judges, **do not print extra text** like "Enter a number:". The checker compares your output exactly with the expected output, so print only what the problem asks for.

> **Practice:** Sum of Two Numbers, Area of a Rectangle, Average of Three Numbers
""",
        },
        {
            "title": "Operators and expressions",
            "content_md": r"""
An **operator** does something with values. An **expression** is values and operators together, like `a + b * 2`.

## Arithmetic operators

| Operator | Meaning |
|---|---|
| `+` `-` `*` | add, subtract, multiply |
| `/` | divide |
| `%` | remainder after division |

```c run
#include <stdio.h>

int main(void) {
    int a = 17, b = 5;
    printf("%d + %d = %d\n", a, b, a + b);
    printf("%d / %d = %d\n", a, b, a / b);
    printf("%d %% %d = %d\n", a, b, a % b);
    printf("Real division: %.2f\n", (float)a / b);
    return 0;
}
```

## Integer division

When both numbers are `int`, `/` gives only the whole part. So `17 / 5` is `3`, not `3.4`. The remainder `2` comes from `17 % 5`.

To get the decimal answer, change one number to `float` first. This is called a **cast**: `(float)a / b`.

To print a real `%` sign, write `%%` inside `printf`.

## Order of work (precedence)

`*`, `/` and `%` are done before `+` and `-`. Use brackets `( )` to choose the order.

```c run
#include <stdio.h>

int main(void) {
    printf("%d\n", 2 + 3 * 4);
    printf("%d\n", (2 + 3) * 4);
    return 0;
}
```

## Shortcuts

```c run
#include <stdio.h>

int main(void) {
    int n = 10;
    n += 5;   // same as n = n + 5
    printf("%d\n", n);
    n++;      // same as n = n + 1
    printf("%d\n", n);
    n *= 2;   // same as n = n * 2
    printf("%d\n", n);
    return 0;
}
```

## Remember

- `int / int` gives an `int`. Cast to `float` when you need decimals.
- `%` gives the remainder. It is very useful: `n % 2 == 0` means `n` is even.

> **Practice:** Average of Three Numbers, Even or Odd
""",
        },
    ],
})

# ---------------------------------------------------------------- Unit 3
UNITS.append({
    "title": "3. Making decisions",
    "lessons": [
        {
            "title": "if, else if and else",
            "content_md": r"""
A program often needs to choose. The `if` statement runs some code only when a condition is true.

## Comparing values

| Operator | Meaning |
|---|---|
| `==` | is equal to |
| `!=` | is not equal to |
| `<` `>` | less than, greater than |
| `<=` `>=` | less than or equal, greater than or equal |

**Warning:** one `=` *puts a value into a variable*. Two `==` *compares*. Mixing them up is a very common mistake.

```c run
#include <stdio.h>

int main(void) {
    int marks;
    scanf("%d", &marks);
    if (marks >= 75) {
        printf("Distinction\n");
    } else if (marks >= 40) {
        printf("Pass\n");
    } else {
        printf("Fail\n");
    }
    return 0;
}
```
```stdin
82
```

Change the input to `55` and then to `20` and see what happens. The computer checks the conditions from top to bottom and runs only the **first** one that is true.

## Even or odd

```c run
#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    if (n % 2 == 0) {
        printf("Even\n");
    } else {
        printf("Odd\n");
    }
    return 0;
}
```
```stdin
7
```

## Joining conditions

- `&&` means **and**: both must be true.
- `||` means **or**: at least one must be true.
- `!` means **not**.

```c run
#include <stdio.h>

int main(void) {
    int age;
    scanf("%d", &age);
    if (age >= 18 && age <= 60) {
        printf("Eligible\n");
    } else {
        printf("Not eligible\n");
    }
    return 0;
}
```
```stdin
25
```

> **Practice:** Even or Odd, Largest of Three, Grade Calculator
""",
        },
        {
            "title": "The switch statement",
            "content_md": r"""
When you compare one variable with many fixed values, `switch` is cleaner than a long chain of `else if`.

```c run
#include <stdio.h>

int main(void) {
    int choice;
    scanf("%d", &choice);

    switch (choice) {
        case 1:
            printf("You chose Tea\n");
            break;
        case 2:
            printf("You chose Coffee\n");
            break;
        case 3:
            printf("You chose Juice\n");
            break;
        default:
            printf("Sorry, we do not have that\n");
    }
    return 0;
}
```
```stdin
2
```

## How it works

- The computer jumps to the `case` that matches the value.
- `break` stops the switch. **If you forget `break`, the computer keeps running the next cases too.** This is called *fall through*.
- `default` runs when no case matches.
- `switch` works with `int` and `char`, not with decimal numbers.

## A calculator

```c run
#include <stdio.h>

int main(void) {
    int a, b;
    char op;
    scanf("%d %c %d", &a, &op, &b);

    switch (op) {
        case '+': printf("%d\n", a + b); break;
        case '-': printf("%d\n", a - b); break;
        case '*': printf("%d\n", a * b); break;
        case '/': printf("%d\n", a / b); break;
        default:  printf("Unknown operator\n");
    }
    return 0;
}
```
```stdin
8 * 7
```

Note the space before `%c` in `"%d %c %d"`. It makes `scanf` skip spaces, so the character is read correctly.

> **Practice:** Grade Calculator
""",
        },
    ],
})

# ---------------------------------------------------------------- Unit 4
UNITS.append({
    "title": "4. Loops",
    "lessons": [
        {
            "title": "while and do-while loops",
            "content_md": r"""
A **loop** repeats code. Computers are very good at repeating things without getting tired.

## The while loop

`while` repeats as long as its condition is true.

```c run
#include <stdio.h>

int main(void) {
    int i = 1;
    while (i <= 5) {
        printf("%d\n", i);
        i++;
    }
    return 0;
}
```

A loop usually has three parts:

1. **Start:** `int i = 1;`
2. **Condition:** `i <= 5`
3. **Change:** `i++`

If you forget the change, the condition never becomes false and the loop runs forever. This is an **infinite loop**. On this website, the program is stopped with *Time limit exceeded*.

```c
while (1) {
    printf("Never stops!\n");
}
```

## Adding numbers with a loop

This program reads numbers until it reads `0`, then prints the total.

```c run
#include <stdio.h>

int main(void) {
    int number, total = 0;
    scanf("%d", &number);
    while (number != 0) {
        total += number;
        scanf("%d", &number);
    }
    printf("Total = %d\n", total);
    return 0;
}
```
```stdin
4 10 6 0
```

## The do-while loop

`do-while` runs the code **first**, then checks the condition. So it always runs at least once.

```c run
#include <stdio.h>

int main(void) {
    int i = 10;
    do {
        printf("i is %d\n", i);
        i++;
    } while (i < 5);
    return 0;
}
```

Even though `i < 5` is false from the start, the message prints once.

> **Practice:** Sum from 1 to N, Count Digits
""",
        },
        {
            "title": "The for loop",
            "content_md": r"""
The `for` loop puts the start, condition and change in one line. Use it when you know how many times to repeat.

```c run
#include <stdio.h>

int main(void) {
    for (int i = 1; i <= 5; i++) {
        printf("%d\n", i);
    }
    return 0;
}
```

Read it as: *start with `i = 1`; while `i <= 5` keep going; after each round do `i++`*.

## Sum of 1 to n

```c run
#include <stdio.h>

int main(void) {
    int n, sum = 0;
    scanf("%d", &n);
    for (int i = 1; i <= n; i++) {
        sum += i;
    }
    printf("Sum = %d\n", sum);
    return 0;
}
```
```stdin
10
```

## A multiplication table

```c run
#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    for (int i = 1; i <= 10; i++) {
        printf("%d x %d = %d\n", n, i, n * i);
    }
    return 0;
}
```
```stdin
7
```

## Counting backwards and in steps

```c run
#include <stdio.h>

int main(void) {
    for (int i = 10; i >= 0; i -= 2) {
        printf("%d ", i);
    }
    printf("\n");
    return 0;
}
```

## break and continue

- `break` leaves the loop immediately.
- `continue` skips the rest of this round and goes to the next one.

```c run
#include <stdio.h>

int main(void) {
    for (int i = 1; i <= 10; i++) {
        if (i % 2 == 0) continue;   // skip even numbers
        if (i > 7) break;           // stop after 7
        printf("%d ", i);
    }
    printf("\n");
    return 0;
}
```

## Which loop should I use?

- Know the number of rounds: `for`.
- Repeat until something happens: `while`.
- Must run at least once: `do-while`.

> **Practice:** Sum from 1 to N, Multiplication Table, Factorial
""",
        },
        {
            "title": "Loops inside loops",
            "content_md": r"""
You can put a loop **inside** another loop. The inner loop runs completely for every single round of the outer loop.
This is how we print patterns and work with tables.

## A star triangle

```c run
#include <stdio.h>

int main(void) {
    int n = 4;
    for (int row = 1; row <= n; row++) {
        for (int star = 1; star <= row; star++) {
            printf("*");
        }
        printf("\n");
    }
    return 0;
}
```

How to read it:

- The outer loop chooses the **row** (1, 2, 3, 4).
- The inner loop prints as many stars as the row number.
- After each row, `printf("\n")` moves to the next line.

Change `n` to 6 and run it again.

## A number grid

```c run
#include <stdio.h>

int main(void) {
    for (int row = 1; row <= 3; row++) {
        for (int col = 1; col <= 4; col++) {
            printf("%d ", row * col);
        }
        printf("\n");
    }
    return 0;
}
```

## Tips for patterns

1. Look at the pattern row by row.
2. Ask: *how many things are in row number `r`?*
3. The answer tells you the limit of the inner loop.

> **Practice:** Triangle Pattern
""",
        },
    ],
})

# ---------------------------------------------------------------- Unit 5
UNITS.append({
    "title": "5. Arrays and strings",
    "lessons": [
        {
            "title": "Arrays",
            "content_md": r"""
What if you need to store the marks of 50 students? Making 50 variables is silly. An **array** stores many values of the same type under one name.

```c run
#include <stdio.h>

int main(void) {
    int marks[5] = {70, 85, 60, 92, 78};
    printf("First mark: %d\n", marks[0]);
    printf("Last mark: %d\n", marks[4]);
    return 0;
}
```

## Index starts at 0

Each value has a position number called an **index**. The first value is at index **0**, not 1. An array of size 5 has indexes 0, 1, 2, 3 and 4. Using index 5 is a bug: the computer may crash or give strange values.

## Using a loop with an array

```c run
#include <stdio.h>

int main(void) {
    int marks[5] = {70, 85, 60, 92, 78};
    int total = 0;
    for (int i = 0; i < 5; i++) {
        total += marks[i];
    }
    printf("Total = %d\n", total);
    printf("Average = %.1f\n", total / 5.0);
    return 0;
}
```

## Reading an array from input

The first number says how many values follow.

```c run
#include <stdio.h>

int main(void) {
    int n, numbers[100];
    scanf("%d", &n);
    for (int i = 0; i < n; i++) {
        scanf("%d", &numbers[i]);
    }

    int largest = numbers[0];
    for (int i = 1; i < n; i++) {
        if (numbers[i] > largest) {
            largest = numbers[i];
        }
    }
    printf("Largest = %d\n", largest);
    return 0;
}
```
```stdin
5
3 9 4 11 7
```

The idea in the middle is very common: start with the first value as the "best so far", then check each other value.

## Printing in reverse

```c run
#include <stdio.h>

int main(void) {
    int a[4] = {1, 2, 3, 4};
    for (int i = 3; i >= 0; i--) {
        printf("%d ", a[i]);
    }
    printf("\n");
    return 0;
}
```

> **Practice:** Reverse an Array
""",
        },
        {
            "title": "Strings",
            "content_md": r"""
In C, a **string** is an array of characters that ends with a special character `'\0'` (the *null character*).
You do not write the `'\0'` yourself when you use double quotes: `"Sankalp"` already has it.

```c run
#include <stdio.h>

int main(void) {
    char name[20] = "Sankalp";
    printf("Hello, %s!\n", name);
    printf("First letter: %c\n", name[0]);
    return 0;
}
```

Use `%s` to print a whole string.

## Reading a word

```c run
#include <stdio.h>
#include <string.h>

int main(void) {
    char word[100];
    scanf("%s", word);
    int length = strlen(word);
    printf("Length: %d\n", length);
    for (int i = length - 1; i >= 0; i--) {
        printf("%c", word[i]);
    }
    printf("\n");
    return 0;
}
```
```stdin
programming
```

- Note there is **no `&`** before `word`. An array name already means "where it is in memory".
- `scanf("%s", ...)` reads one word and stops at a space.
- `strlen(word)` from `<string.h>` gives the number of characters.
- Make the array big enough. A word of 99 letters needs `char word[100]` (one place for `'\0'`).

## Going through every character

This program counts vowels.

```c run
#include <stdio.h>

int main(void) {
    char text[100];
    scanf("%s", text);
    int vowels = 0;
    for (int i = 0; text[i] != '\0'; i++) {
        char c = text[i];
        if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u') {
            vowels++;
        }
    }
    printf("Vowels: %d\n", vowels);
    return 0;
}
```
```stdin
education
```

The loop stops when it reaches `'\0'`.

## Challenge

This program counts only small letters. In the practice problem you must also count capital letters. Hint: a capital `'A'` is different from `'a'`. You can write both in the condition.

> **Practice:** Count Vowels
""",
        },
    ],
})

# ---------------------------------------------------------------- Unit 6
UNITS.append({
    "title": "6. Functions and pointers",
    "lessons": [
        {
            "title": "Functions",
            "content_md": r"""
A **function** is a named block of code that you can use again and again. You have already used two: `printf` and `main`.
Now you will make your own.

```c run
#include <stdio.h>

int square(int x) {
    return x * x;
}

int main(void) {
    printf("%d\n", square(5));
    printf("%d\n", square(12));
    return 0;
}
```

## The parts of a function

```c
int square(int x) {
    return x * x;
}
```

- `int` before the name is the **return type**: what the function gives back.
- `square` is the name.
- `int x` is a **parameter**: a value the function receives.
- `return` sends the result back to whoever called it.

A function that gives back nothing uses `void`.

```c run
#include <stdio.h>

void greet(void) {
    printf("Welcome to Sankalp AI!\n");
}

int main(void) {
    greet();
    greet();
    return 0;
}
```

## A function that decides

```c run
#include <stdio.h>

int is_even(int n) {
    return n % 2 == 0;
}

int max_of(int a, int b) {
    if (a > b) {
        return a;
    }
    return b;
}

int main(void) {
    printf("%d\n", is_even(8));
    printf("%d\n", is_even(7));
    printf("%d\n", max_of(14, 9));
    return 0;
}
```

In C, `1` means true and `0` means false.

## Order matters

The computer reads the file from top to bottom. A function must be written **before** it is used, or you must write a **prototype** (just the first line, with `;`) at the top:

```c run
#include <stdio.h>

int cube(int x);   // prototype

int main(void) {
    printf("%d\n", cube(3));
    return 0;
}

int cube(int x) {
    return x * x * x;
}
```

## Functions get copies

When you pass a variable, the function receives a **copy**. Changing the copy does not change the original.

```c run
#include <stdio.h>

void try_to_change(int x) {
    x = 100;
}

int main(void) {
    int a = 5;
    try_to_change(a);
    printf("a is still %d\n", a);
    return 0;
}
```

The next lesson shows how to change the original with pointers.

> **Practice:** Factorial, Prime Check
""",
        },
        {
            "title": "Pointers: a first look",
            "content_md": r"""
Every variable lives at a place in memory. That place has an **address**. A **pointer** is a variable that stores an address.

- `&x` means *the address of `x`*.
- `int *p` declares a pointer to an `int`.
- `*p` means *the value at the address in `p`*.

```c run
#include <stdio.h>

int main(void) {
    int x = 10;
    int *p = &x;      // p points to x

    printf("x is %d\n", x);
    printf("*p is %d\n", *p);

    *p = 99;          // change x through the pointer
    printf("x is now %d\n", x);
    return 0;
}
```

Now you can see why `scanf` needs `&`: it needs the **address** so it can put the value there.

## Changing the original inside a function

Last lesson a function received a copy. If we pass an **address**, the function can change the original.

```c run
#include <stdio.h>

void swap(int *x, int *y) {
    int temp = *x;
    *x = *y;
    *y = temp;
}

int main(void) {
    int a = 5, b = 9;
    swap(&a, &b);
    printf("a = %d, b = %d\n", a, b);
    return 0;
}
```

## Remember

- `&` gets an address. `*` follows an address.
- Pointers are a big topic. If this feels hard, that is normal. Come back to it after you have done the other practice problems.

## What next?

You now know the basics of C: input and output, decisions, loops, arrays, strings and functions.
Go to **Problems** and solve the practice problems. Solving problems is how programming is really learned.
""",
        },
    ],
})
