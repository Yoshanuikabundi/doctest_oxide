"""
Unit and regression test for the doctest_oxide package.
"""

# Import package, test suite, and other packages as needed
import sys

import pytest

import doctest_oxide


def test_doctest_oxide_imported():
    """Sample test, will always pass so long as import statement worked."""
    assert "doctest_oxide" in sys.modules


def test_leading_spaces():
    assert doctest_oxide.leading_spaces("     hi there") == 5
    assert doctest_oxide.leading_spaces("//     hi there") == 0
    assert doctest_oxide.leading_spaces("//     hi there     ") == 0
    assert doctest_oxide.leading_spaces("  \t  hi there     ") == 2


def test_get_common_indent():
    text = [
        "foo",
        "  bar",
        "baz",
    ]

    assert doctest_oxide.get_common_indent(*text) == 0

    text = [
        "  foo",
        "    bar",
        "  baz",
    ]

    assert doctest_oxide.get_common_indent(*text) == 2


def test_pythoncode_1():
    code = [
        "// import foo",
        "   for f in foo():",
        "       print(f)",
        "//     foo.bar()",
        "",
        "   os.exit()",
    ]

    pcode = doctest_oxide.PythonCode(code)

    assert pcode.to_exec() == "\n".join(
        [
            "import foo",
            "for f in foo():",
            "    print(f)",
            "    foo.bar()",
            "",
            "os.exit()",
        ]
    )

    assert pcode.to_vis() == "\n".join(
        [
            "for f in foo():",
            "    print(f)",
            "",
            "os.exit()",
        ]
    )


def test_pythoncode_2():
    code = [
        "// import foo",
        "for f in foo():",
        "    print(f)",
        "    // foo.bar()",
        "",
        "os.exit()",
    ]

    pcode = doctest_oxide.PythonCode(code)

    assert pcode.to_exec() == "\n".join(
        [
            "import foo",
            "for f in foo():",
            "    print(f)",
            "    foo.bar()",
            "",
            "os.exit()",
        ]
    )

    assert pcode.to_vis() == "\n".join(
        [
            "for f in foo():",
            "    print(f)",
            "",
            "os.exit()",
        ]
    )


def test_pythoncode_3():
    code = [
        "// import pytest",
        "// with pytest.raises(ValueError):",
        "       raise ValueError('This is helpful')",
        "       // print('This should not print')",
        "",
    ]

    pcode = doctest_oxide.PythonCode(code)

    assert pcode.to_exec() == "\n".join(
        [
            "import pytest",
            "with pytest.raises(ValueError):",
            "    raise ValueError('This is helpful')",
            "    print('This should not print')",
            "",
        ]
    )

    assert pcode.to_vis() == "\n".join(
        [
            "raise ValueError('This is helpful')",
            "",
        ]
    )
