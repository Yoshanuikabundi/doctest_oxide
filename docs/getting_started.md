# Getting Started

This page details how to get started with doctest_oxide. 

```python
print("hello world")
``` 

```python
// message = "hello world"
print(message)
``` 

```python
// with open("README.md") as readme:
      readme.read()
``` 

```python
// import pytest
// with pytest.raises(ValueError):
      raise ValueError("BORKED")
``` 


Syntax errors fail pytest with an error message, but it could use some finessing.
Change this from `text` to `python` to see.
```text
this test fails too
``` 

Exceptions fail pytest too.
Change this from `text` to `python` to see.
```text
1
2
3
4
5
56
raise ValueError("This test fails")
``` 