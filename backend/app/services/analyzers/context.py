from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from ...models import (
    CommitInfo,
    DependenciesSection,
    ReadmeSection,
    RepoInfo,
    Risk,
    StartupSection,
)
from ..file_index import FileIndex
from ..platform.base import PlatformAdapter
from ..platform.parser import ParsedRepo


@dataclass
class AnalyzerContext:
    parsed: ParsedRepo
    repo: RepoInfo
    commit: CommitInfo
    index: FileIndex
    adapter: PlatformAdapter
    readme_text: str | None = None
    readme: ReadmeSection | None = None
    dependencies: DependenciesSection | None = None
    startup: StartupSection | None = None

    def source_url(self, path: str | None, line: int | None = None) -> str | None:
        if not path:
            return None
        return self.adapter.blob_url(self.parsed, self.commit.sha, path, line)


@dataclass
class AnalyzerOutput:
    section: BaseModel
    risks: list[Risk] = field(default_factory=list)
    score: int = 0
    reasons: list[str] = field(default_factory=list)
