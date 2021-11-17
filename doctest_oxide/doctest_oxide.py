from typing import Union, Iterable, Set, Optional, Dict, List, Any, Sequence
import os
import sys
import traceback as tb
from code import compile_command, InteractiveInterpreter

from sphinx.application import Sphinx
from sphinx.builders import Builder
from sphinx.environment import BuildEnvironment
from sphinx.transforms import SphinxTransform

import docutils.nodes

import pytest
from _pytest._code.code import ExceptionInfo, TerminalRepr


def node_lang_is_python(node: docutils.nodes.literal_block) -> bool:
    # TODO: Improve handling of "default"
    python_synonyms = {
        "default",
        "python",
        "py",
        "py3",
        "python3",
    }

    return node.attributes["language"] in python_synonyms


def leading_spaces(s: str) -> int:
    """Return the number of spaces at the start of str"""
    return len(s) - len(s.lstrip(" "))


def get_common_indent(*lines: str) -> int:
    return min(leading_spaces(l) for l in lines if l)


def whitespaceify_hidden_markers(*lines: str) -> Iterable[str]:
    """Convert "//" markers at the start of a line to '  '"""
    for line in lines:
        if line.strip().startswith("//"):
            line = line.replace("//", "  ", 1)
        yield line


def remove_hidden_markers(*lines: str) -> Iterable[str]:
    """Remove "//" markers and the following whitespace at the start of a line"""
    for line in lines:
        if line.strip().startswith("//"):
            before, _, after = line.partition("//")
            line = before + after.lstrip()
        yield line


class PythonCode:
    """Processes text from a literal block into a test or codeblock

    First, lines are collected and any common indent consisting of whitespace or
    hidden markers ("//") is removed. Then, any remaining hidden markers are removed,
    along with any whitespace between the hidden marker and the code."""

    def __init__(
        self, text: Union[str, List[str], docutils.nodes.Node], lineno: int = 0
    ):
        if isinstance(text, str):
            lines = text.splitlines()
            if text.endswith("\n"):
                lines.append("")
        elif isinstance(text, list) and all(isinstance(s, str) for s in text):
            lines: List[str] = text
        else:
            raise ValueError("Text must be str or list of strs")
        self._orig_lines = lines

        self._line_number = lineno

        self._hidden_lines = [l.strip().startswith("//") for l in lines]

        indent = get_common_indent(*whitespaceify_hidden_markers(*lines))
        lines = [line[indent:] for line in lines]
        self._lines = list(remove_hidden_markers(*lines))

    @classmethod
    def from_node(cls, node: docutils.nodes.literal_block) -> "PythonCode":
        if not isinstance(node, docutils.nodes.literal_block):
            raise ValueError(f"Node {node} is not a literal block")
        if not node_lang_is_python(node):
            raise ValueError(f"Node {node} is not in the Python language")

        return cls(node.astext(), node.line)

    def __str__(self) -> str:
        return "\n".join(self._orig_lines)

    def __repr__(self) -> str:
        return f"PythonCode('{self.__str__()}')"

    def to_exec(self) -> str:
        """Get the code that should be executed in a test"""
        return "\n".join(self._lines)

    def to_vis(self) -> str:
        hiddens = self._hidden_lines
        lines = [line for line, hidden in zip(self._lines, hiddens) if not hidden]

        common_indent = get_common_indent(*lines)
        return "\n".join(l[common_indent:] for l in lines)

    @property
    def raw_source(self) -> str:
        return "\n".join(self._orig_lines)


class TestCollectionVisitor(docutils.nodes.SparseNodeVisitor):
    def __init__(self, document):
        self.tests: Dict[
            int, str
        ] = {}  # Maps line numbers to the tests that start there
        self.document = document

    def unknown_visit(self, node: docutils.nodes.Node):
        pass

    def visit_literal_block(self, node: docutils.nodes.literal_block):
        if node_lang_is_python(node):
            content = PythonCode.from_node(node)
            new_content = content.to_vis()
            assert len(node.children) == 1
            node.replace(node.children[0], docutils.nodes.Text(new_content))
            node.rawsource = new_content
            self.tests[node.line] = content.to_exec()


class DoctestOxideTransform(SphinxTransform):
    default_priority = 750

    def apply(self, **kwargs: Any) -> None:
        visitor = TestCollectionVisitor(self.document)
        self.document.walk(visitor)
        docname = self.env.docname
        self.env.doctest_oxide_data[docname] = visitor.tests


def env_purge_doc_callback(app: Sphinx, env: BuildEnvironment, docname: str):
    data = {}
    try:
        data = env.doctest_oxide_data
    except AttributeError:
        env.doctest_oxide_data = data

    data[docname] = {}


def env_merge_info_callback(
    app: Sphinx,
    env: BuildEnvironment,
    docnames: List[str],
    other: BuildEnvironment,
):
    other_data = other.doctest_oxide_data

    for docname in docnames:
        env.doctest_oxide_data[docname] = other_data[docname]


def invoke_pytest_callback(app: Sphinx, exception: Optional[Exception]):
    if exception is not None:
        return

    data = app.env.doctest_oxide_data

    pytest.main([], plugins=[PytestPlugin(data)])


class DoctestItem(pytest.Item):
    def __init__(self, name, code: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.code = code

    def runtest(self) -> None:
        code = compile_command(self.code, filename="<doctest>", symbol="exec")
        if code is None:
            raise ValueError("Code is incomplete")
        interpreter = InteractiveInterpreter()
        interpreter.runcode(code)

    # def repr_failure(
    #     self, excinfo: ExceptionInfo[BaseException]
    # ) -> Union[str, TerminalRepr]:
    #     exception = excinfo.value
    #     traceback = excinfo.traceback

    #     out = exception, exception.__dict__, type(exception)
    #     print(traceback)

    #     return str(out)


class DoctestCollector(pytest.Collector):
    def __init__(self, name: str, data: Dict[str, Dict[int, str]], **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.data = data

    def collect(self) -> Iterable[Union["pytest.Item", "pytest.Collector"]]:
        items = []
        for docname, tests in self.data.items():
            for lineno, test in tests.items():
                item = DoctestItem.from_parent(
                    self, name=f"{docname}:{lineno}", code=test
                )
                items.append(item)
        return items


class PytestPlugin:
    def __init__(self, data: Dict[str, Dict[int, str]]) -> None:
        self.data = data

    def pytest_collection(self, session: pytest.Session):
        collector = DoctestCollector.from_parent(
            session, name="doctest-collector", data=self.data
        )

        items = collector.collect()

        session.testscollected = len(items)
        session.items = items

        return session


def setup(app: Sphinx):

    app.add_transform(DoctestOxideTransform)
    app.connect("env-purge-doc", env_purge_doc_callback)
    app.connect("env-merge-info", env_merge_info_callback)
    app.connect("build-finished", invoke_pytest_callback)

    return {
        "version": "0.1",
        # The extensions have to increment the version when data structure has changed. If not given,
        # Sphinx considers the extension does not stores any data to environment.
        "env_version": "1",
        # A parallel_read_safe=True extension must satisfy the following conditions:
        #   - The core logic of the extension is parallelly executable during the reading phase.
        #   - It has event handlers for env-merge-info and env-purge-doc events if it stores data
        #     to the build environment object (env) during the reading phase.
        "parallel_read_safe": True,
        # A parallel_write_safe=True extension must satisfy the following conditions:
        #   - The core logic of the extension is parallelly executable during the writing phase.
        "parallel_write_safe": True,
    }
