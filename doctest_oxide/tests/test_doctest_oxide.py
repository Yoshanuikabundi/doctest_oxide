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
