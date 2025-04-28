"""A helper module for version control system operations."""

import os
import subprocess
import time
from datetime import datetime
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod


class VCSInterface(ABC):
    """Abstract base class defining the interface for VCS operations."""
    name = None

    @abstractmethod
    def is_used(self, file_path) -> bool:
        """Check if this VCS is used in the given file."""
        pass

    @abstractmethod
    def get_file_creator(self, file_path):
        """Get the creator of a file."""
        pass
    
    @abstractmethod
    def get_last_modifier(self, file_path):
        """Get the last person who modified a file."""
        pass
    
    @abstractmethod
    def get_line_author(self, file_path, line_number):
        """Get the author of a specific line."""
        pass
    
    @abstractmethod
    def get_line_commit_message(self, file_path, line_number):
        """Get the commit message for a specific line."""
        pass
    
    @abstractmethod
    def get_file_history(self, file_path, limit=5):
        """Get file history (last N changes)."""
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
                return {
                    'name': author,
                    'email': email,
                    'timestamp': int(timestamp),
                    'date': datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
                }
        except (subprocess.SubprocessError, ValueError, IndexError):
            return None, "Could not determine file creator"
        
        return None, "No creator information found"
    
    def get_last_modifier(self, file_path):
        """Get the last person who modified a file in Git."""
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%an|%ae|%at', '--', file_path],
                capture_output=True, text=True, check=True
            )
            if result.stdout.strip():
                author, email, timestamp = result.stdout.strip().split('|')
                return {
                    'name': author,
                    'email': email,
                    'timestamp': int(timestamp),
                    'date': datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
                }
        except (subprocess.SubprocessError, ValueError):
            return None, "Could not determine last modifier"
        
        return None, "No modifier information found"
    
    def get_line_author(self, file_path, line_number):
        """Get the author of a specific line in Git."""
        if not line_number:
            return None, "No line number provided"
        
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
            
            if author:
                return {
                    'name': author,
                    'email': email,
                    'timestamp': timestamp,
                    'date': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp else "unknown"
                }
        except subprocess.SubprocessError:
            return None, "Could not determine line author"
        
        return None, "No line author information found"
    
    def get_line_commit_message(self, file_path, line_number):
        """Get the commit message for a specific line in Git."""
        if not line_number:
            return None, "No line number provided"
        
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
            return None, "Could not determine commit message"

    def get_file_history(self, file_path, limit=5):
        """Get file history (last N changes) in Git."""
        history = []
        
        try:
            result = subprocess.run(
                ['git', 'log', f'-{limit}', '--pretty=format:%h|%an|%ae|%at|%s', '--', file_path],
                capture_output=True, text=True, check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('|', 4)
                    if len(parts) == 5:
                        hash_val, author, email, timestamp, subject = parts
                        history.append({
                            'hash': hash_val,
                            'author': author,
                            'email': email,
                            'timestamp': int(timestamp),
                            'date': datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S'),
                            'subject': subject
                        })
        except subprocess.SubprocessError:
            return None, "Could not retrieve file history"
        
        return history

class SVNVCS(VCSInterface):
    """SVN implementation of the VCS interface."""
    name = "svn"

    def is_used(self, file_path) -> bool:
        """Check if SVN is used for the given file."""
        try:
            result = subprocess.run(['svn', 'info', file_path], 
                                   capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            pass  # SVN command not found
        return False

    def get_file_creator(self, file_path):
        """Get the creator of a file in SVN."""
        try:
            result = subprocess.run(
                ['svn', 'log', '--xml', '--limit', '1', '--revision', '1:HEAD', file_path],
                capture_output=True, text=True, check=True
            )
            
            # Parse XML output to extract author and date
            root = ET.fromstring(result.stdout)
            entry = root.find('.//logentry')
            if entry is not None:
                author = entry.find('author').text
                date_str = entry.find('date').text
                
                # Parse ISO 8601 date
                try:
                    timestamp = time.mktime(time.strptime(date_str[:19], '%Y-%m-%dT%H:%M:%S'))
                    date_formatted = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    timestamp = None
                    date_formatted = "unknown"
                    
                return {
                    'name': author,
                    'email': f"{author}@your-domain.com",  # SVN doesn't store emails by default
                    'timestamp': timestamp,
                    'date': date_formatted
                }
        except (subprocess.SubprocessError, ET.ParseError):
            return None, "Could not determine file creator"
        
        return None, "No creator information found"
    
    def get_last_modifier(self, file_path):
        """Get the last person who modified a file in SVN."""
        try:
            result = subprocess.run(
                ['svn', 'info', file_path],
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
                try:
                    # Format is typically: "2023-04-15 10:30:45 +0000 (Sat, 15 Apr 2023)"
                    date_part = date_str.split('(')[0].strip()
                    timestamp = time.mktime(time.strptime(date_part[:19], '%Y-%m-%d %H:%M:%S'))
                    date_formatted = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    timestamp = None
                    date_formatted = "unknown"
                    
                return {
                    'name': author,
                    'email': f"{author}@your-domain.com",  # SVN doesn't store emails by default
                    'timestamp': timestamp,
                    'date': date_formatted
                }
        except subprocess.SubprocessError:
            return None, "Could not determine last modifier"
        
        return None, "No modifier information found"
    
    def get_line_author(self, file_path, line_number):
        """Get the author of a specific line in SVN."""
        if not line_number:
            return None, "No line number provided"
        
        try:
            # Get blame information
            result = subprocess.run(
                ['svn', 'blame', file_path],
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
                        ['svn', 'log', '-r', revision, file_path],
                        capture_output=True, text=True, check=True
                    )
                    
                    date_str = None
                    for log_line in log_result.stdout.split('\n'):
                        if log_line.startswith('r') and '|' in log_line:
                            date_str = log_line.split('|')[2].strip()
                            break
                    
                    # Parse date string
                    timestamp = None
                    date_formatted = "unknown"
                    if date_str:
                        try:
                            timestamp = time.mktime(time.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S'))
                            date_formatted = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            pass
                            
                    return {
                        'name': author,
                        'email': f"{author}@your-domain.com",  # SVN doesn't store emails by default
                        'timestamp': timestamp,
                        'date': date_formatted,
                        'revision': revision
                    }
        except subprocess.SubprocessError:
            return None, "Could not determine line author"
        
        return None, "No line author information found"
    
    def get_line_commit_message(self, file_path, line_number):
        """Get the commit message for a specific line in SVN."""
        if not line_number:
            return None, "No line number provided"
        
        try:
            # First get the revision for this line
            blame_result = subprocess.run(
                ['svn', 'blame', file_path],
                capture_output=True, text=True, check=True
            )
            
            lines = blame_result.stdout.split('\n')
            if 0 <= line_number - 1 < len(lines):
                blame_line = lines[line_number - 1]
                revision = blame_line.strip().split()[0]
                
                # Now get the commit message
                log_result = subprocess.run(
                    ['svn', 'log', '-r', revision, file_path],
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
            return None, "Could not determine commit message"
        
        return None, "No commit message found"
    
    def get_file_history(self, file_path, limit=5):
        """Get file history (last N changes) in SVN."""
        history = []
        
        try:
            result = subprocess.run(
                ['svn', 'log', '--limit', str(limit), file_path],
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
                        timestamp = None
                        date_formatted = "unknown"
                        try:
                            timestamp = time.mktime(time.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S'))
                            date_formatted = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            pass
                            
                        history.append({
                            'revision': revision,
                            'author': author,
                            'email': f"{author}@your-domain.com",
                            'timestamp': timestamp,
                            'date': date_formatted,
                            'message': message
                        })
        except subprocess.SubprocessError:
            return None, "Could not retrieve file history"
        
        return history

class VCSHelper:
    def __init__(self, handlers=None):
        if handlers is None:
            handlers = [SVNVCS(), GitVCS()]
        self.handlers = handlers

    def detect_vcs(self, path):
        """Detect which version control system is being used."""
        h = self.get_vcs_handler(path)
        return h.name if h else None

    def get_vcs_handler(self, path):
        """Get the appropriate VCS implementation based on the repository type."""
        for handler in self.handlers:
            if handler.is_used(path):
                return handler
        return None

    def get_file_creator(self, file_path):
        """Get the creator of a file."""
        vcs_handler = self.get_vcs_handler(os.path.dirname(file_path))
        if not vcs_handler:
            return None, "No version control system detected"
        
        return vcs_handler.get_file_creator(file_path)

    def get_last_modifier(self, file_path):
        """Get the last person who modified a file."""
        vcs_handler = self.get_vcs_handler(os.path.dirname(file_path))
        if not vcs_handler:
            return None, "No version control system detected"
        
        return vcs_handler.get_last_modifier(file_path)

    def get_line_author(self, file_path, line_number):
        """Get the author of a specific line."""
        vcs_handler = self.get_vcs_handler(os.path.dirname(file_path))
        if not vcs_handler:
            return None, "No version control system detected"
        
        return vcs_handler.get_line_author(file_path, line_number)

    def get_line_commit_message(self, file_path, line_number):
        """Get the commit message for a specific line."""
        vcs_handler = self.get_vcs_handler(os.path.dirname(file_path))
        if not vcs_handler:
            return None, "No version control system detected"
        
        return vcs_handler.get_line_commit_message(file_path, line_number)

    def get_file_history(self, file_path, limit=5):
        """Get file history (last N changes)."""
        vcs_handler = self.get_vcs_handler(os.path.dirname(file_path))
        if not vcs_handler:
            return None, "No version control system detected"
        
        return vcs_handler.get_file_history(file_path, limit)
