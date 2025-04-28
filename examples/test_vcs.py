# test_vcs.py
import os
from micropytest.vcs_helper import VCSHelper
from micropytest.decorators import tag

# You could use custom VCS by passing the handlers argument to the constructor to supply a list of
# VCSInterface implementations
vcs_helper = VCSHelper()


@tag('vcs', 'git', 'integration')
def test_vcs_helper(ctx):
    """Run a test that dumps VCS information about this file."""
    # Get the path of the current file
    current_file = os.path.abspath(__file__)
    
    ctx.info(f"VCS Test")
    ctx.info(f"=============")
    ctx.info(f"Testing file: {current_file}")
    
    # Detect VCS
    vcs_type = vcs_helper.detect_vcs(os.path.dirname(current_file))
    ctx.info(f"Version Control System: {vcs_type or 'None detected'}")
    
    # Test the VCS detection
    assert vcs_type is not None, "VCS type should be detected"
    
    # Get file creator info
    ctx.info("File Creator Information:")
    creator = vcs_helper.get_file_creator(current_file)
    if creator and not isinstance(creator, tuple):
        ctx.info(f"  Created by: {creator['name']}")
        ctx.info(f"  Email: {creator['email']}")
        ctx.info(f"  Creation date: {creator['date']}")
        # Store creator info as an artifact
        ctx.add_artifact("file_creator", creator)
        
        # Add an assertion to verify creator info
        assert creator['name'], "Creator name should not be empty"
    else:
        error_msg = creator[1] if isinstance(creator, tuple) else "Unknown error"
        ctx.warn(f"  Could not determine file creator: {error_msg}")
    
    # Get last modifier info
    ctx.info("Last Modifier Information:")
    last_modifier = vcs_helper.get_last_modifier(current_file)
    if last_modifier and not isinstance(last_modifier, tuple):
        ctx.info(f"  Last modified by: {last_modifier['name']}")
        ctx.info(f"  Email: {last_modifier['email']}")
        ctx.info(f"  Last modified on: {last_modifier['date']}")
        # Store last modifier info as an artifact
        ctx.add_artifact("last_modifier", last_modifier)
    else:
        error_msg = last_modifier[1] if isinstance(last_modifier, tuple) else "Unknown error"
        ctx.error(f"  Could not determine last modifier: {error_msg}")
    
    # Get info about this function's code
    ctx.info("Current Function Information:")
    # Find the approximate line number of this function
    try:
        with open(current_file, 'r') as f:
            lines = f.readlines()
        
        function_line = 0
        for i, line in enumerate(lines, 1):
            if "def test_vcs_helper" in line:
                function_line = i
                break
        
        if function_line > 0:
            ctx.info(f"  Function starts at line: {function_line}")
            
            # Get author of this function
            line_author = vcs_helper.get_line_author(current_file, function_line)
            if line_author and not isinstance(line_author, tuple):
                ctx.info(f"  Function written by: {line_author['name']}")
                ctx.info(f"  Email: {line_author['email']}")
                ctx.info(f"  Written on: {line_author['date']}")
                
                # Get commit message
                commit_msg = vcs_helper.get_line_commit_message(current_file, function_line)
                if commit_msg and not isinstance(commit_msg, tuple):
                    ctx.info(f"  Commit message: {commit_msg}")
                    # Store function author info as an artifact
                    ctx.add_artifact("function_author", {
                        "author": line_author,
                        "commit_message": commit_msg
                    })
            else:
                error_msg = line_author[1] if isinstance(line_author, tuple) else "Unknown error"
                ctx.error(f"  Could not determine function author: {error_msg}")
        else:
            ctx.warn("  Could not locate function line number")
    except Exception as e:
        ctx.error(f"  Error analyzing function: {str(e)}")
    
    # Get file history
    ctx.info("File History (last 5 changes):")
    history = vcs_helper.get_file_history(current_file, 5)
    if history and not isinstance(history, tuple):
        history_entries = []
        for i, entry in enumerate(history, 1):
            entry_info = f"  {i}. "
            if 'hash' in entry:  # Git
                entry_info += f"{entry['hash']} - {entry['author']} ({entry['date']})"
                ctx.info(entry_info)
                ctx.info(f"     {entry['subject']}")
            else:  # SVN
                entry_info += f"r{entry['revision']} - {entry['author']} ({entry['date']})"
                ctx.info(entry_info)
                ctx.info(f"     {entry['message']}")
            history_entries.append(entry)
        # Store history as an artifact
        ctx.add_artifact("file_history", history_entries)
    else:
        error_msg = history[1] if isinstance(history, tuple) else "Unknown error"
        ctx.error(f"  Could not retrieve file history: {error_msg}")
    
    # Test for specific line ranges
    ctx.info("Line-by-Line Analysis:")
    
    # Sample a few lines from the file
    try:
        with open(current_file, 'r') as f:
            lines = f.readlines()
        
        # Sample lines at different parts of the file
        sample_lines = [
            1,  # First line
            min(20, len(lines)),  # Around line 20
            min(len(lines) // 2, len(lines)),  # Middle of file
            len(lines)  # Last line
        ]
        
        line_analysis = {}
        for line_num in sample_lines:
            ctx.info(f"\n  Line {line_num}: {lines[line_num-1].strip()}")
            line_author = vcs_helper.get_line_author(current_file, line_num)
            
            if line_author and not isinstance(line_author, tuple):
                ctx.info(f"    Author: {line_author['name']}")
                ctx.info(f"    Last modified: {line_author['date']}")
                line_analysis[line_num] = line_author
            else:
                error_msg = line_author[1] if isinstance(line_author, tuple) else "Unknown error"
                ctx.error(f"    Could not determine line author: {error_msg}")
        
        # Store line analysis as an artifact
        ctx.add_artifact("line_analysis", line_analysis)
    except Exception as e:
        ctx.error(f"  Error in line-by-line analysis: {str(e)}")
