# vcs_helper.py
# A helper module for version control system operations

import os
import subprocess
import time
from datetime import datetime
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod


class VCSInterface(ABC):
    """Abstract base class defining the interface for VCS operations."""
    
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
        
        return None, "No commit message found"
    
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

class VCSHelper:
    @staticmethod
    def detect_vcs(path):
        """Detect which version control system is being used."""
        # Check for SVN
        try:
            result = subprocess.run(['svn', 'info', path], 
                                   capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return "svn"
        except FileNotFoundError:
            pass  # SVN command not found
            
        # Check for Git
        try:
            result = subprocess.run(['git', '-C', path, 'rev-parse', '--is-inside-work-tree'], 
                                   capture_output=True, text=True, check=False)
            if result.returncode == 0 and "true" in result.stdout:
                return "git"
        except FileNotFoundError:
            pass  # Git command not found
            
        return None

    @staticmethod
    def get_vcs_handler(path):
        """Get the appropriate VCS implementation based on the repository type."""
        vcs_type = VCSHelper.detect_vcs(path)
        
        if vcs_type == "git":
            return GitVCS()
        elif vcs_type == "svn":
            return SVNVCS()
        else:
            return None

    @staticmethod
    def get_file_creator(file_path):
        """Get the creator of a file."""
        vcs_handler = VCSHelper.get_vcs_handler(os.path.dirname(file_path))
        if not vcs_handler:
            return None, "No version control system detected"
        
        return vcs_handler.get_file_creator(file_path)

    @staticmethod
    def get_last_modifier(file_path):
        """Get the last person who modified a file."""
        vcs_handler = VCSHelper.get_vcs_handler(os.path.dirname(file_path))
        if not vcs_handler:
            return None, "No version control system detected"
        
        return vcs_handler.get_last_modifier(file_path)

    @staticmethod
    def get_line_author(file_path, line_number):
        """Get the author of a specific line."""
        vcs_handler = VCSHelper.get_vcs_handler(os.path.dirname(file_path))
        if not vcs_handler:
            return None, "No version control system detected"
        
        return vcs_handler.get_line_author(file_path, line_number)

    @staticmethod
    def get_line_commit_message(file_path, line_number):
        """Get the commit message for a specific line."""
        vcs_handler = VCSHelper.get_vcs_handler(os.path.dirname(file_path))
        if not vcs_handler:
            return None, "No version control system detected"
        
        return vcs_handler.get_line_commit_message(file_path, line_number)

    @staticmethod
    def get_file_history(file_path, limit=5):
        """Get file history (last N changes)."""
        vcs_handler = VCSHelper.get_vcs_handler(os.path.dirname(file_path))
        if not vcs_handler:
            return None, "No version control system detected"
        
        return vcs_handler.get_file_history(file_path, limit)