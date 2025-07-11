"""A helper module for version control system operations."""

import subprocess
import time
from datetime import datetime
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Optional
import os
from os import PathLike
from dataclasses import dataclass
from pathlib import Path
import re

@dataclass
class VCSInfo:
    name: str
    email: Optional[str]
    timestamp: int

    @property
    def date(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')


@dataclass
class VCSHistoryEntry:
    revision: str
    author: VCSInfo
    message: str


@dataclass
class Change:
    path: str  # relative path with / as separator
    type: str  # file, dir
    operation: str  # add, delete, modify


@dataclass
class ChangeSet:
    """Represents a set of changed files or directories."""
    items: list[Change]
    root: str  # absolute path

    def has_changes(self, relative_path: PathLike) -> bool:
        """Check if the given relative path (file or directory) has changes.

        A directory has changed if any items in it (recursively) have changed (add, delete, modify).
        A file has changed if occurs in the list of items.
        A file or directory has also changed if any of its parents have been added or deleted.
        """
        relative_path = self._normalize_path(relative_path)
        for item in self.items:
            if item.path == relative_path or item.path.startswith(relative_path + '/'):
                # item itself or descendant has changed
                return True

        # check if any parent has been added or deleted
        parent = os.path.dirname(relative_path)
        while parent != '':
            for item in self.items:
                if item.path == parent and item.type == 'dir' and item.operation in ['add', 'delete']:
                    return True
            parent = os.path.dirname(parent)
        return False

    def list_changes(self, location: PathLike, type: Optional[str] = None) -> list[str]:
        """Get the list of changed items (files or directories) directly under the given location.

        If type == "dir" only list directories, if type == "file" only list files.
        """
        location = os.path.abspath(str(location))
        changed = []
        for item in os.scandir(location):
            if (type is None) or (type == "dir" and item.is_dir()) or (type == "file" and item.is_file()):
                relative_path = os.path.relpath(item.path, self.root)
                if self.has_changes(relative_path):
                    changed.append(item.name)
        return changed

    def _normalize_path(self, path: PathLike) -> str:
        path = os.path.normpath(str(path))
        path = path.replace('\\', '/')
        if path.endswith('/'):
            path = path[:-1]
        return path


class VCSInterface(ABC):
    """Abstract base class defining the interface for VCS operations."""
    name = None

    @abstractmethod
    def is_used(self, file_path: PathLike) -> bool:
        """Check if this VCS is used in the given file."""
        pass

    @abstractmethod
    def get_file_creator(self, file_path: PathLike) -> VCSInfo:
        """Get the creator of a file."""
        pass

    @abstractmethod
    def get_last_modifier(self, file_path: PathLike) -> VCSInfo:
        """Get the last person who modified a file."""
        pass

    @abstractmethod
    def get_line_author(self, file_path: PathLike, line_number: int) -> VCSInfo:
        """Get the author of a specific line."""
        pass

    @abstractmethod
    def get_line_commit_message(self, file_path: PathLike, line_number: int) -> str:
        """Get the commit message for a specific line."""
        pass

    @abstractmethod
    def get_file_history(self, file_path: PathLike, limit: int = 5) -> list[VCSHistoryEntry]:
        """Get file history (last N changes)."""
        pass

    @abstractmethod
    def get_last_commit(self, repo_path: PathLike) -> VCSHistoryEntry:
        """Get information about the last commit."""
        pass

    @abstractmethod
    def get_changes(self, repo_path: PathLike, revision: str) -> ChangeSet:
        """Get changes (relative to repo path) of a given commit, with respect to the previous commit."""
        pass

    @abstractmethod
    def get_repo_root(self, path: PathLike) -> str:
        """Get the root directory of the repository, given any path inside the repository."""
        pass

    @abstractmethod
    def get_branch(self, repo_path: PathLike) -> str:
        """Get current branch name, given repo root directory."""
        pass


class VCSError(Exception):
    """Exception raised for VCS errors."""
    pass


class GitVCS(VCSInterface):
    """Git implementation of the VCS interface."""
    name = "git"

    def is_used(self, file_path) -> bool:
        """Check if Git is used for the given file."""
        try:
            result = subprocess.run(['git', '-C', file_path, 'rev-parse', '--is-inside-work-tree'],
                                   capture_output=True, text=True, check=False)
            if result.returncode == 0 and "true" in result.stdout:
                return True
        except FileNotFoundError:
            pass  # Git command not found
        return False

    def get_file_creator(self, file_path):
        """Get the creator of a file in Git."""
        try:
            result = subprocess.run(
                ['git', 'log', '--format=%an|%ae|%at', '--reverse', '--', file_path],
                capture_output=True, text=True, check=True
            )
            first_line = result.stdout.strip().split('\n')[0]
            if first_line:
                author, email, timestamp = first_line.split('|')
                return VCSInfo(
                    name=author,
                    email=email,
                    timestamp=int(timestamp),
                )
        except (subprocess.SubprocessError, ValueError, IndexError):
            pass

        raise VCSError("Could not determine file creator")

    def get_last_modifier(self, file_path):
        """Get the last person who modified a file in Git."""
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%an|%ae|%at', '--', file_path],
                capture_output=True, text=True, check=True
            )
            if result.stdout.strip():
                author, email, timestamp = result.stdout.strip().split('|')
                return VCSInfo(
                    name=author,
                    email=email,
                    timestamp=int(timestamp),
                )
        except (subprocess.SubprocessError, ValueError):
            pass

        raise VCSError("Could not determine last modifier")

    def get_line_author(self, file_path, line_number):
        """Get the author of a specific line in Git."""
        try:
            result = subprocess.run(
                ['git', 'blame', '-L', f"{line_number},{line_number}", '--porcelain', file_path],
                capture_output=True, text=True, check=True
            )

            author = None
            email = None
            timestamp = None
            for line in result.stdout.split('\n'):
                if line.startswith('author '):
                    author = line[7:].strip()
                elif line.startswith('author-mail '):
                    email = line[12:].strip().strip('<>')
                elif line.startswith('author-time '):
                    timestamp = int(line[11:].strip())
            if author is None or email is None or timestamp is None:
                raise VCSError("Could not determine line author")

            return VCSInfo(
                name=author,
                email=email,
                timestamp=timestamp,
            )
        except subprocess.SubprocessError:
            pass

        raise VCSError("No line author information found")

    def get_line_commit_message(self, file_path, line_number):
        """Get the commit message for a specific line in Git."""
        try:
            # First get the commit hash for this line
            blame_result = subprocess.run(
                ['git', 'blame', '-L', f"{line_number},{line_number}", '--porcelain', file_path],
                capture_output=True, text=True, check=True
            )

            commit_hash = blame_result.stdout.split('\n')[0].split(' ')[0]

            # Now get the commit message
            msg_result = subprocess.run(
                ['git', 'show', '-s', '--format=%B', commit_hash],
                capture_output=True, text=True, check=True
            )

            return msg_result.stdout.strip()
        except subprocess.SubprocessError:
            raise VCSError("Could not determine commit message")

    def get_file_history(self, file_path, limit=5):
        """Get file history (last N changes) in Git."""
        history: list[VCSHistoryEntry] = []

        try:
            result = subprocess.run(
                ['git', 'log', f'-{limit}', '--pretty=format:%H|%an|%ae|%at|%s', '--', file_path],
                capture_output=True, text=True, check=True
            )

            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('|', 4)
                    if len(parts) == 5:
                        hash_val, author, email, timestamp, message = parts
                        history.append(VCSHistoryEntry(
                            revision=hash_val,
                            author=VCSInfo(name=author, email=email, timestamp=int(timestamp)),
                            message=message,
                        ))
        except subprocess.SubprocessError:
            raise VCSError("Could not retrieve file history")

        return history

    def get_last_commit(self, repo_path: PathLike) -> VCSHistoryEntry:
        """Get information about the last commit."""
        return self.get_file_history(repo_path, limit=1)[0]

    def get_changes(self, repo_path: PathLike, revision: str) -> ChangeSet:
        """Get changes (relative to repo path) of a given commit, with respect to the previous commit."""
        # Previous commit in Git = first parent commit (i.e. the previous state of the branch that was merged into)
        # In Git all changes are files
        # Rename is shown as delete and add
        repo_path = Path(repo_path).resolve()

        try:
            result = subprocess.run(
                ["git", "diff", "--name-status", revision + "^", revision],
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            raise VCSError(f"Git command failed: {e.stderr.strip()}") from e

        changes: list[Change] = []

        for line in result.stdout.strip().splitlines():
            if not line:
                continue

            parts = line.split("\t")
            status = parts[0]

            if status == "A":
                path = parts[1]
                operation = "add"
                changes.append(Change(path=path, type="file", operation=operation))
            elif status == "D":
                path = parts[1]
                operation = "delete"
                changes.append(Change(path=path, type="file", operation=operation))
            elif status == "M":
                path = parts[1]
                operation = "modify"
                changes.append(Change(path=path, type="file", operation=operation))
            elif status.startswith("R"):  # Rename
                old_path, new_path = parts[1], parts[2]
                changes.append(Change(path=old_path, type="file", operation="delete"))
                changes.append(Change(path=new_path, type="file", operation="add"))
            else:
                raise VCSError(f"Git: unexpected output line: {line}")

        return ChangeSet(items=changes, root=str(repo_path))

    def get_repo_root(self, path: PathLike) -> str:
        """Get the root directory of the repository, given any path inside the repository."""
        path = os.path.abspath(str(path))
        if not os.path.exists(path):
            raise VCSError(f"Path does not exist: {path}")
        if not os.path.isdir(path):
            path = os.path.dirname(path)
        return subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=path).decode("utf-8").strip()

    def get_branch(self, repo_path: PathLike) -> str:
        """Get current branch name, given repo root directory."""
        return subprocess.check_output(["git", "branch", "--show-current"], cwd=repo_path).decode("utf-8").strip()


class SVNVCS(VCSInterface):
    """SVN implementation of the VCS interface."""
    name = "svn"

    def is_used(self, file_path) -> bool:
        """Check if SVN is used for the given file."""
        try:
            flags = self._get_flags()
            file_url = self._get_file_url(file_path)
            rev = self._get_working_copy_revision(file_path)
            result = subprocess.run(arg('svn', 'info', *flags, "-r", rev, file_url), capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.CalledProcessError, VCSError):
            pass
        return False

    def get_file_creator(self, file_path):
        """Get the creator of a file in SVN."""
        try:
            flags = self._get_flags()
            file_url = self._get_file_url(file_path)
            result = subprocess.run(
                arg('svn', 'log', *flags, '--xml', '--limit', '1', '--revision', '1:HEAD', file_url),
                capture_output=True, text=True, check=True
            )

            # Parse XML output to extract author and date
            root = ET.fromstring(result.stdout)
            entry = root.find('.//logentry')
            if entry is not None:
                author = entry.find('author').text
                date_str = entry.find('date').text

                # Parse ISO 8601 date
                timestamp = int(time.mktime(time.strptime(date_str[:19], '%Y-%m-%dT%H:%M:%S')))

                return VCSInfo(
                    name=author,
                    email=None,  # SVN doesn't store emails by default
                    timestamp=timestamp,
                )
        except (subprocess.SubprocessError, ET.ParseError):
            pass

        raise VCSError("Could not determine file creator")

    def get_last_modifier(self, file_path):
        """Get the last person who modified a file in SVN."""
        try:
            flags = self._get_flags()
            file_url = self._get_file_url(file_path)
            rev = self._get_working_copy_revision(file_path)
            result = subprocess.run(
                arg('svn', 'info', *flags, "-r", rev, file_url),
                capture_output=True, text=True, check=True
            )

            author = None
            date_str = None

            for line in result.stdout.split('\n'):
                if line.startswith('Last Changed Author:'):
                    author = line.split(':', 1)[1].strip()
                elif line.startswith('Last Changed Date:'):
                    date_str = line.split(':', 1)[1].strip()

            if author and date_str:
                # Parse date string
                # Format is typically: "2023-04-15 10:30:45 +0000 (Sat, 15 Apr 2023)"
                date_part = date_str.split('(')[0].strip()
                timestamp = int(time.mktime(time.strptime(date_part[:19], '%Y-%m-%d %H:%M:%S')))

                return VCSInfo(
                    name=author,
                    email=None,  # SVN doesn't store emails by default
                    timestamp=timestamp,
                )
        except subprocess.SubprocessError:
            pass

        raise VCSError("Could not determine last modifier")

    def get_line_author(self, file_path, line_number):
        """Get the author of a specific line in SVN."""
        try:
            # Get blame information
            flags = self._get_flags()
            file_url = self._get_file_url(file_path)
            rev = self._get_working_copy_revision(file_path)
            result = subprocess.run(
                arg('svn', 'blame', *flags, "-r", rev, file_url),
                capture_output=True, text=True, check=True
            )

            lines = result.stdout.split('\n')
            if 0 <= line_number - 1 < len(lines):
                blame_line = lines[line_number - 1]
                parts = blame_line.strip().split()
                if len(parts) >= 2:
                    revision = parts[0]
                    author = parts[1]

                    # Get revision date
                    log_result = subprocess.run(
                        arg('svn', 'log', *flags, '-r', revision, file_url),
                        capture_output=True, text=True, check=True
                    )

                    date_str = None
                    for log_line in log_result.stdout.split('\n'):
                        if log_line.startswith('r') and '|' in log_line:
                            date_str = log_line.split('|')[2].strip()
                            break
                    if date_str is None:
                        raise VCSError("Could not determine line author date")

                    # Parse date string
                    timestamp = int(time.mktime(time.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')))

                return VCSInfo(
                    name=author,
                    email=None,  # SVN doesn't store emails by default
                    timestamp=timestamp,
                )
        except subprocess.SubprocessError:
            pass

        raise VCSError("Could not determine line author")

    def get_line_commit_message(self, file_path, line_number) -> str:
        """Get the commit message for a specific line in SVN."""
        try:
            # First get the revision for this line
            flags = self._get_flags()
            file_url = self._get_file_url(file_path)
            rev = self._get_working_copy_revision(file_path)
            blame_result = subprocess.run(
                arg('svn', 'blame', *flags, "-r", rev, file_url),
                capture_output=True, text=True, check=True
            )

            lines = blame_result.stdout.split('\n')
            if 0 <= line_number - 1 < len(lines):
                blame_line = lines[line_number - 1]
                revision = blame_line.strip().split()[0]

                # Now get the commit message
                log_result = subprocess.run(
                    arg('svn', 'log', *flags, '-r', revision, file_url),
                    capture_output=True, text=True, check=True
                )

                # Extract message from log output
                log_lines = log_result.stdout.split('\n')
                if len(log_lines) >= 4:
                    # Skip header lines and get the message
                    message_lines = []
                    for i in range(3, len(log_lines)):
                        if log_lines[i].startswith('----------'):
                            break
                        message_lines.append(log_lines[i])

                    return '\n'.join(message_lines).strip()
        except subprocess.SubprocessError:
            pass

        raise VCSError("Could not determine commit message")

    def _get_repo_url(self, file_path):
        # get repo file url
        flags = self._get_flags()
        repo_root = self.get_repo_root(file_path)
        url_result = subprocess.run(
            arg('svn', 'info', *flags, '--show-item', 'url', repo_root),
            capture_output=True, text=True, check=True
        )
        return url_result.stdout.strip()
    
    def _get_file_url(self, file_path):
        abs_path = os.path.abspath(file_path)
        repo_root = self.get_repo_root(file_path)
        rel_path = os.path.relpath(abs_path, repo_root).replace('\\', '/')
        url = self._get_repo_url(file_path)
        if not url.endswith('/'):
            url += '/'
        if rel_path.startswith('./'):
            rel_path = rel_path[2:]
        if rel_path == '.':
            rel_path = ''
        return url + rel_path
    
    def _get_working_copy_revision(self, file_path):
        flags = self._get_flags()
        repo_root = self.get_repo_root(file_path)
        url_result = subprocess.run(
            arg('svn', 'info', *flags, '--show-item', 'revision', repo_root),
            capture_output=True, text=True, check=True
        )
        return url_result.stdout.strip()

    def get_file_history(self, file_path, limit=5):
        """Get file history (last N changes) in SVN."""
        history: list[VCSHistoryEntry] = []

        try:
            flags = self._get_flags()
            url = self._get_file_url(file_path)

            # running this with url instead of working copy path also works correctly for directories
            result = subprocess.run(
                arg('svn', 'log', *flags, '--limit', str(limit), url),
                capture_output=True, text=True, check=True
            )

            # Parse SVN log output
            entries = result.stdout.split('-' * 72)
            for entry in entries:
                if not entry.strip():
                    continue

                lines = entry.strip().split('\n')
                if len(lines) >= 2:
                    header = lines[0]
                    message = '\n'.join(lines[1:]).strip()

                    # Parse header line (r123 | user | date | lines)
                    header_parts = header.split('|')
                    if len(header_parts) >= 3:
                        revision = header_parts[0].strip().lstrip('r')
                        author = header_parts[1].strip()
                        date_str = header_parts[2].strip()

                        # Parse date string
                        timestamp = int(time.mktime(time.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')))

                        history.append(VCSHistoryEntry(
                            revision=revision,
                            author=VCSInfo(name=author, email=None, timestamp=timestamp),
                            message=message,
                        ))
        except subprocess.SubprocessError:
            raise VCSError("Could not retrieve file history")

        return history

    def get_last_commit(self, repo_path: PathLike) -> VCSHistoryEntry:
        """Get information about the last commit."""
        return self.get_file_history(repo_path, limit=1)[0]

    def get_changes(self, repo_path: PathLike, revision: str) -> ChangeSet:
        """Get changes (relative to repo path) of a given commit, with respect to the previous commit."""
        revision = str(revision)
        repo_path = Path(repo_path)
        url = self._get_repo_url(repo_path)
        if not url.endswith('/'):
            url += '/'

        try:
            flags = self._get_flags()
            result = subprocess.run(
                arg("svn", "log", *flags, "-v", "-r", revision),
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            raise VCSError(f"SVN command failed: {e.stderr.strip()}") from e

        changed = []
        in_changed_paths = False

        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("Changed paths:"):
                in_changed_paths = True
                continue
            if in_changed_paths:
                if not line or not re.match(r'^[MAD] ', line):
                    break  # End of changed paths section

                match = re.match(r"([MAD])\s+(\/\S+)", line)
                if not match:
                    raise VCSError(f"Could not parse svn log output: {line}")

                action, path = match.groups()

                # Normalize the path (remove '/trunk/' prefix)
                trunk_prefix = "/trunk/"
                if not path.startswith(trunk_prefix):
                    if path == trunk_prefix[:-1]:
                        continue
                    raise VCSError(f"Only trunk changes are supported, got: {path}")
                rel_path = path[len(trunk_prefix):]
                full_path = url + rel_path

                # Determine operation
                operation = {"A": "add", "M": "modify", "D": "delete"}[action]

                if action == "M":
                    # Modified items are always files
                    changed.append(Change(path=rel_path, operation=operation, type="file"))

                elif action == "A":
                    # Use svn info to check whether it's a file
                    info_result = subprocess.run(
                        arg("svn", "info", *flags, f"{full_path}@{revision}"),
                        cwd=repo_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=True
                    )
                    t = "file" if "Node Kind: file" in info_result.stdout else "dir"
                    changed.append(Change(path=rel_path, operation=operation, type=t))

                elif action == "D":
                    # Check previous revision to determine what was deleted
                    prev_revision = str(int(revision) - 1)
                    parent, name = os.path.split(full_path)
                    assert '\\' not in parent + name

                    ls_result = subprocess.run(
                        arg("svn", "ls", *flags, f"{parent}@{prev_revision}"),
                        cwd=repo_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=True
                    )
                    items = ls_result.stdout.strip().splitlines()
                    isfile = any(entry.strip("/") == name and not entry.endswith("/") for entry in items)
                    t = "file" if isfile else "dir"
                    changed.append(Change(path=rel_path, operation=operation, type=t))

        return ChangeSet(items=changed, root=os.path.abspath(str(repo_path)))

    def get_repo_root(self, path: PathLike) -> str:
        """Get the root directory of the repository, given any path inside the repository."""
        # get root of the working copy
        path = os.path.abspath(str(path))
        original_path = path
        if not os.path.exists(path):
            raise VCSError(f"Path does not exist: {path}")
        if not os.path.isdir(path):
            path = os.path.dirname(path)
        flags = self._get_flags()
        is_root = False
        while True:
            try:
                output = subprocess.check_output(
                    arg("svn", "info", *flags, "--show-item", "wc-root", path), cwd=path, stderr=subprocess.PIPE
                )
                return output.decode("utf-8").strip()
            except subprocess.CalledProcessError:
                if is_root:
                    raise VCSError(f"Could not find SVN root for {original_path}")
                # try parent directory
                path = os.path.dirname(path)
                if path == os.path.dirname(path):
                    is_root = True

    def get_branch(self, repo_path: PathLike) -> str:
        """Get current branch name, given repo root directory."""
        url = self._get_repo_url(repo_path)
        return url.split('/')[-1]

    def _get_credentials(self) -> list[str]:
        username = os.environ.get("SVN_USERNAME", "")
        password = os.environ.get("SVN_PASSWORD", "")
        if username == "" or password == "":
            return []
        return ["--username", username, "--password", password]

    def _get_flags(self) -> list[str]:
        return self._get_credentials() + ["--non-interactive"]


class VCSHelper:
    def __init__(self, handlers=None):
        if handlers is None:
            handlers = [SVNVCS(), GitVCS()]
        self.handlers = handlers

    def detect_vcs(self, path) -> Optional[str]:
        """Detect which version control system is being used."""
        h = self.get_vcs_handler(path)
        return h.name if h else None

    def get_vcs_handler(self, path) -> Optional[VCSInterface]:
        """Get the appropriate VCS implementation based on the repository type."""
        for handler in self.handlers:
            if handler.is_used(path):
                return handler
        return None


def arg(*args):
    return list(args)
