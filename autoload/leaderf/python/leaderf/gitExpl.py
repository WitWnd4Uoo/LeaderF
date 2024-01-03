#!/usr/bin/env python
# -*- coding: utf-8 -*-

import vim
import re
import os
import os.path
import json
import itertools
from enum import Enum
from functools import wraps
from collections import OrderedDict
from collections import deque
from .utils import *
from .explorer import *
from .manager import *
from .devicons import (
    webDevIconsGetFileTypeSymbol,
    removeDevIcons,
    matchaddDevIconsDefault,
    matchaddDevIconsExact,
    matchaddDevIconsExtension,
)

#*****************************************************
# GitExplorer
#*****************************************************
class GitExplorer(Explorer):
    def __init__(self):
        self._executor = []
        self._display_multi = False
        self._show_icon = lfEval("get(g:, 'Lf_ShowDevIcons', 1)") == "1"

    def getContent(self, *args, **kwargs):
        commands = lfEval("leaderf#Git#Commands()")
        return [list(item)[0] for item in commands]

    def formatLine(self, line):
        pass

    def getStlCategory(self):
        return 'Git'

    def getStlCurDir(self):
        return escQuote(lfEncode(lfGetCwd()))

    def supportsNameOnly(self):
        return False

    def cleanup(self):
        for exe in self._executor:
            exe.killProcess()
        self._executor = []

    def getPatternRegex(self):
        return self._pattern_regex

    def getContextSeparator(self):
        return self._context_separator

    def displayMulti(self):
        return self._display_multi


class GitDiffExplorer(GitExplorer):
    def __init__(self):
        super(GitDiffExplorer, self).__init__()
        self._source_info = {}

    def getContent(self, *args, **kwargs):
        arguments_dict = kwargs.get("arguments", {})

        executor = AsyncExecutor()
        self._executor.append(executor)

        self._source_info = {}

        cmd = "git diff --no-color --raw --no-abbrev"
        if "--cached" in arguments_dict:
            cmd += " --cached"
        if "extra" in arguments_dict:
            cmd += " " + " ".join(arguments_dict["extra"])
        content = executor.execute(cmd, encoding=lfEval("&encoding"), format_line=self.formatLine)
        return content

    def formatLine(self, line):
        """
        :000000 100644 000000000 5b01d33aa A    runtime/syntax/json5.vim
        :100644 100644 671b269c0 ef52cddf4 M    runtime/syntax/nix.vim
        :100644 100644 69671c59c 084f8cdb4 M    runtime/syntax/zsh.vim
        :100644 100644 b90f76fc1 bad07e644 R099 src/version.c   src/version2.c
        :100644 000000 b5825eb19 000000000 D    src/testdir/dumps

        ':100644 100644 72943a1 dbee026 R050\thello world.txt\thello world2.txt'
        """
        tmp = line.split(sep='\t')
        file_names = (tmp[1], tmp[2] if len(tmp) == 3 else "")
        blob_status = tmp[0].split()
        self._source_info[file_names] = (blob_status[2], blob_status[3], blob_status[4],
                                         file_names[0], file_names[1])
        icon = webDevIconsGetFileTypeSymbol(file_names[0]) if self._show_icon else ""
        return "{:<4} {}{}{}".format(blob_status[4], icon, file_names[0],
                                     "" if file_names[1] == "" else "\t->\t" + file_names[1] )

    def getStlCategory(self):
        return 'Git_diff'

    def getSourceInfo(self):
        return self._source_info


class GitLogExplorer(GitExplorer):
    def getContent(self, *args, **kwargs):
        arguments_dict = kwargs.get("arguments", {})

        executor = AsyncExecutor()
        self._executor.append(executor)

        cmd = 'git log --pretty=format:"%h%d %s"'
        if ("--current-file" in arguments_dict
            and vim.current.buffer.name
            and not vim.current.buffer.options['bt']
           ):
            file_name = vim.current.buffer.name
            if " " in file_name:
                file_name = file_name.replace(' ', r'\ ')
            cmd += " -- {}".format(file_name)

        if "extra" in arguments_dict:
            cmd += " " + " ".join(arguments_dict["extra"])
        content = executor.execute(cmd, encoding=lfEval("&encoding"), format_line=self.formatLine)
        return content

    def formatLine(self, line):
        return line

    def getStlCategory(self):
        return 'Git_log'


class GitCommand(object):
    def __init__(self, arguments_dict, source):
        self._arguments = arguments_dict
        self._source = source
        self._cmd = ""
        self._file_type_cmd = ""
        self._buffer_name = ""
        self.buildCommandAndBufferName()

    def buildCommandAndBufferName(self):
        pass

    def getCommand(self):
        return self._cmd

    def getFileTypeCommand(self):
        return self._file_type_cmd

    def getBufferName(self):
        return self._buffer_name

    def getArguments(self):
        return self._arguments

    def getSource(self):
        return self._source


class GitDiffCommand(GitCommand):
    def __init__(self, arguments_dict, source):
        super(GitDiffCommand, self).__init__(arguments_dict, source)

    def buildCommandAndBufferName(self):
        self._cmd = "git diff --no-color"
        extra_options = ""
        if "--cached" in self._arguments:
            extra_options += " --cached"

        if "extra" in self._arguments:
            extra_options += " " + " ".join(self._arguments["extra"])

        if self._source is not None:
            file_name = self._source[3] if self._source[4] == "" else self._source[4]
            if " " in file_name:
                file_name = file_name.replace(' ', r'\ ')
            extra_options += " -- {}".format(file_name)
        elif ("--current-file" in self._arguments
              and vim.current.buffer.name
              and not vim.current.buffer.options['bt']
             ):
            file_name = vim.current.buffer.name
            if " " in file_name:
                file_name = file_name.replace(' ', r'\ ')
            extra_options += " -- {}".format(lfRelpath(file_name))

        self._cmd += extra_options
        self._buffer_name = "LeaderF://git diff" + extra_options
        self._file_type_cmd = "silent! doautocmd filetypedetect BufNewFile *.diff"


class GitCatFileCommand(GitCommand):
    def __init__(self, arguments_dict, source):
        """
        source is a tuple like (b90f76fc1, R099, src/version.c)
        """
        super(GitCatFileCommand, self).__init__(arguments_dict, source)

    @staticmethod
    def buildBufferName(source):
        """
        source is a tuple like (b90f76fc1, R099, src/version.c)
        """
        return "{}:{}".format(source[0][:9], source[2])

    def buildCommandAndBufferName(self):
        self._cmd = "git cat-file -p {}".format(self._source[0])
        if self._source[0].startswith("0000000"):
            if self._source[1] == "M":
                if os.name == 'nt':
                    self._cmd = "type {}".format(self._source[2])
                else:
                    self._cmd = "cat {}".format(self._source[2])
            else:
                self._cmd = ""

        self._buffer_name = GitCatFileCommand.buildBufferName(self._source)
        self._file_type_cmd = "silent! doautocmd filetypedetect BufNewFile {}".format(self._source[2])


class GitLogCommand(GitCommand):
    def __init__(self, arguments_dict, source):
        super(GitLogCommand, self).__init__(arguments_dict, source)

    def buildCommandAndBufferName(self):
        if "--directly" in self._arguments:
            self._cmd = "git log"

            if "extra" in self._arguments:
                self._cmd += " " + " ".join(self._arguments["extra"])

            if ("--current-file" in self._arguments
                and vim.current.buffer.name
                and not vim.current.buffer.options['bt']
               ):
                file_name = vim.current.buffer.name
                if " " in file_name:
                    file_name = file_name.replace(' ', r'\ ')
                self._cmd += " -- {}".format(lfRelpath(file_name))

            self._buffer_name = "LeaderF://" + self._cmd
            self._file_type_cmd = "setlocal filetype=git"
        else:
            sep = ' ' if os.name == 'nt' else ''
            self._cmd = ('git show {} --pretty=format:"tree   %T%nparent %P%n'
                         'author %an <%ae> %ad%ncommitter %cn <%ce> %cd{}%n%n%s%n%n%b%n"'
                         ' --stat=70 --stat-graph-width=10 -p --no-color'
                         ).format(self._source, sep)
            self._buffer_name = "LeaderF://" + self._source
            self._file_type_cmd = "setlocal filetype=git"


class GitLogExplCommand(GitCommand):
    def __init__(self, arguments_dict, source):
        super(GitLogExplCommand, self).__init__(arguments_dict, source)

    def buildCommandAndBufferName(self):
        self._cmd = ('git show -m --raw -C --numstat --shortstat '
                     '--pretty=format:"# %P" --no-abbrev {}').format(self._source)
        self._buffer_name = "LeaderF://navigation/" + self._source
        self._file_type_cmd = ""


class ParallelExecutor(object):
    @staticmethod
    def run(*cmds):
        outputs = [[] for _ in range(len(cmds))]
        stop_thread = False

        def readContent(content, output):
            try:
                for line in content:
                    output.append(line)
                    if stop_thread:
                        break
            except Exception as e:
                print(e)


        executors = [AsyncExecutor() for _ in range(len(cmds))]
        workers = []
        for i, (exe, cmd) in enumerate(zip(executors, cmds)):
            content = exe.execute(cmd.getCommand(), encoding=lfEval("&encoding"))
            worker = threading.Thread(target=readContent, args=(content, outputs[i]))
            worker.daemon = True
            worker.start()
            workers.append(worker)

        for w in workers:
            w.join(5) # I think 5s is enough for git cat-file

        stop_thread = True

        for e in executors:
            e.killProcess()

        return outputs


class GitCommandView(object):
    def __init__(self, owner, cmd, window_id):
        self._owner = owner
        self._cmd = cmd
        self._window_id = window_id
        self._executor = AsyncExecutor()
        self._buffer = None
        self.init()
        owner.register(self)

    def init(self):
        self._content = []
        self._timer_id = None
        self._reader_thread = None
        self._offset_in_content = 0
        self._read_finished = 0
        self._stop_reader_thread = False

    def getBufferName(self):
        return self._cmd.getBufferName()

    def getWindowId(self):
        return self._window_id

    def getContent(self):
        return self._content

    def setContent(self, content):
        try:
            self._buffer.options['modifiable'] = True
            self._buffer[:] = content
        finally:
            self._buffer.options['modifiable'] = False

    def getSource(self):
        return self._cmd.getSource()

    def start(self):
        # start a process, timer and thread
        content = self._executor.execute(self._cmd.getCommand(), encoding=lfEval("&encoding"))

        self._timer_id = lfEval("timer_start(100, function('leaderf#Git#WriteBuffer', [%d]), {'repeat': -1})" % id(self))

        self._reader_thread = threading.Thread(target=self._readContent, args=(content,))
        self._reader_thread.daemon = True
        self._reader_thread.start()

    def setOptions(self, bufhidden):
        lfCmd("call win_execute({}, 'setlocal nobuflisted')".format(self._window_id))
        lfCmd("call win_execute({}, 'setlocal buftype=nofile')".format(self._window_id))
        lfCmd("call win_execute({}, 'setlocal bufhidden={}')".format(self._window_id, bufhidden))
        lfCmd("call win_execute({}, 'setlocal undolevels=-1')".format(self._window_id))
        lfCmd("call win_execute({}, 'setlocal noswapfile')".format(self._window_id))
        lfCmd("call win_execute({}, 'setlocal nospell')".format(self._window_id))
        lfCmd("call win_execute({}, 'setlocal nomodifiable')".format(self._window_id))
        lfCmd("call win_execute({}, '{}')".format(self._window_id, self._cmd.getFileTypeCommand()))

    def initBuffer(self):
        pass

    def defineMaps(self, winid):
        pass

    def create(self, bufhidden='wipe', buf_content=None):
        if self._buffer is not None:
            self._buffer.options['modifiable'] = True
            del self._buffer[:]
            self._buffer.options['modifiable'] = False
            self.cleanup()
            lfCmd("call win_gotoid({})".format(self._window_id))

        self.init()

        if self._buffer is None:
            self.defineMaps(self._window_id)
            self.setOptions(bufhidden)
            if bufhidden == 'wipe':
                lfCmd("augroup Lf_Git | augroup END")
                lfCmd("call win_execute({}, 'autocmd! Lf_Git BufWipeout <buffer> call leaderf#Git#Suicide({})')"
                      .format(self._window_id, id(self)))

        self._buffer = vim.buffers[int(lfEval("winbufnr({})".format(self._window_id)))]

        if buf_content is not None:
            # cache the content if buf_content is the result of ParallelExecutor.run()
            self._content = buf_content
            self._owner.readFinished(self)

            self._read_finished = 2

            self._buffer.options['modifiable'] = True
            self._buffer[:] = buf_content
            self._buffer.options['modifiable'] = False

            self._owner.writeFinished(self._window_id)
            return

        if self._cmd.getCommand() == "":
            self._read_finished = 2
            self._owner.writeFinished(self._window_id)
            return

        self.initBuffer()
        self.start()


    def writeBuffer(self):
        if self._read_finished == 2:
            return

        if not self._buffer.valid:
            self.stopTimer()
            return

        self._buffer.options['modifiable'] = True
        try:
            cur_len = len(self._content)
            if cur_len > self._offset_in_content:
                if self._offset_in_content == 0:
                    self._buffer[:] = self._content[:cur_len]
                else:
                    self._buffer.append(self._content[self._offset_in_content:cur_len])

                self._offset_in_content = cur_len
                lfCmd("redraw")
        finally:
            self._buffer.options['modifiable'] = False

        if self._read_finished == 1 and self._offset_in_content == len(self._content):
            self._read_finished = 2
            self._owner.writeFinished(self._window_id)
            self.stopTimer()

    def _readContent(self, content):
        try:
            for line in content:
                self._content.append(line)
                if self._stop_reader_thread:
                    break
            else:
                self._read_finished = 1
                self._owner.readFinished(self)
        except Exception as e:
            self._read_finished = 1
            print(e)

    def stopThread(self):
        if self._reader_thread and self._reader_thread.is_alive():
            self._stop_reader_thread = True
            self._reader_thread.join(0.01)

    def stopTimer(self):
        if self._timer_id is not None:
            lfCmd("call timer_stop(%s)" % self._timer_id)
            self._timer_id = None

    def cleanup(self):
        self.stopTimer()
        self.stopThread()
        # must do this at last
        self._executor.killProcess()

    def suicide(self):
        self._owner.deregister(self)

    def valid(self):
        return self._buffer is not None and self._buffer.valid


class LfOrderedDict(OrderedDict):
    def last_key(self):
        return next(reversed(self.keys()))

    def last_value(self):
        return next(reversed(self.values()))

    def last_key_value(self):
        return next(reversed(self.items()))


class FolderStatus(Enum):
    CLOSED = 0
    OPEN = 1


class TreeNode(object):
    def __init__(self, status=FolderStatus.OPEN):
        self.status = status
        # key is the directory name, value is a TreeNode
        self.dirs = LfOrderedDict()
        # key is the file name,
        # value is a tuple like (b90f76fc1, bad07e644, R099, src/version.c, src/version2.c)
        self.files = LfOrderedDict()


class MetaInfo(object):
    def __init__(self, level, is_dir, name, info, path):
        """
        info is TreeNode if is_dir is true or source otherwise.
        """
        self.level = level
        self.is_dir = is_dir
        self.name = name
        self.info = info
        self.path = path


class TreeView(GitCommandView):
    def __init__(self, owner, cmd, window_id, project_root):
        super(TreeView, self).__init__(owner, cmd, window_id)
        self._project_root = project_root
        # key is the parent hash, value is a TreeNode
        self._trees = LfOrderedDict()
        # key is the parent hash, value is a list of MetaInfo
        self._file_structures = {}
        # to protect self._file_structures
        self._lock = threading.Lock()
        self._current_parent = None
        self._short_stat = {}
        self._num_stat = {}
        folder_icons = lfEval("g:Lf_GitFolderIcons")
        self._closed_folder_icon = folder_icons["closed"]
        self._open_folder_icon = folder_icons["open"]
        self._preopen_num = int(lfEval("get(g:, 'Lf_GitPreopenNum', 0)"))
        self._add_icon = lfEval("get(g:, 'Lf_GitAddIcon', '')")    #  
        self._copy_icon = lfEval("get(g:, 'Lf_GitCopyIcon', '')")
        self._del_icon = lfEval("get(g:, 'Lf_GitDelIcon', '')")    #  
        self._modification_icon = lfEval("get(g:, 'Lf_GitModificationIcon', '')")
        self._rename_icon = lfEval("get(g:, 'Lf_GitRenameIcon', '')")
        self._status_icons = {
                "A": self._add_icon,
                "C": self._copy_icon,
                "D": self._del_icon,
                "M": self._modification_icon,
                "R": self._rename_icon,
                }
        self._head = [
                '" Press <F1> for help',
                '',
                ]
        self._match_ids = []
        self.enableColor()

    def enableColor(self):
        lfCmd(r"""call win_execute({}, 'let matchid = matchadd(''Lf_hl_gitFolder'', ''\S*/'', 10)')"""
              .format(self._window_id))
        id = int(lfEval("matchid"))
        self._match_ids.append(id)
        lfCmd(r"""call win_execute({}, 'let matchid = matchadd(''Lf_hl_gitFolderIcon'', ''^\s*\zs[{}{}]'', 10)')"""
              .format(self._window_id, self._closed_folder_icon, self._open_folder_icon))
        id = int(lfEval("matchid"))
        self._match_ids.append(id)
        lfCmd(r"""call win_execute({}, 'let matchid = matchadd(''Lf_hl_gitAddIcon'', ''^\s*\zs{}'', 10)')"""
              .format(self._window_id, self._add_icon))
        id = int(lfEval("matchid"))
        self._match_ids.append(id)
        lfCmd(r"""call win_execute({}, 'let matchid = matchadd(''Lf_hl_gitCopyIcon'', ''^\s*\zs{}'', 10)')"""
              .format(self._window_id, self._copy_icon))
        id = int(lfEval("matchid"))
        self._match_ids.append(id)
        lfCmd(r"""call win_execute({}, 'let matchid = matchadd(''Lf_hl_gitDelIcon'', ''^\s*\zs{}'', 10)')"""
              .format(self._window_id, self._del_icon))
        id = int(lfEval("matchid"))
        self._match_ids.append(id)
        lfCmd(r"""call win_execute({}, 'let matchid = matchadd(''Lf_hl_gitModificationIcon'', ''^\s*\zs{}'', 10)')"""
              .format(self._window_id, self._modification_icon))
        id = int(lfEval("matchid"))
        self._match_ids.append(id)
        lfCmd(r"""call win_execute({}, 'let matchid = matchadd(''Lf_hl_gitRenameIcon'', ''^\s*\zs{}'', 10)')"""
              .format(self._window_id, self._rename_icon))
        id = int(lfEval("matchid"))
        self._match_ids.append(id)
        lfCmd(r"""call win_execute({}, 'let matchid = matchadd(''Lf_hl_gitNumStatAdd'', ''\t\zs+\d\+'', 10)')"""
              .format(self._window_id))
        id = int(lfEval("matchid"))
        self._match_ids.append(id)
        lfCmd(r"""call win_execute({}, 'let matchid = matchadd(''Lf_hl_gitNumStatDel'', ''\t+\d\+\s\+\zs-\d\+'', 10)')"""
              .format(self._window_id))
        id = int(lfEval("matchid"))
        self._match_ids.append(id)
        lfCmd(r"""call win_execute({}, 'let matchid = matchadd(''Lf_hl_gitNumStatBinary'', ''\t\zs(Bin)'', 10)')"""
              .format(self._window_id))
        id = int(lfEval("matchid"))
        self._match_ids.append(id)

    def defineMaps(self, winid):
        lfCmd("call win_execute({}, 'call leaderf#Git#TreeViewMaps({})')"
              .format(self._window_id, id(self)))

    def generateSource(self, line):
        """
        :000000 100644 000000000 5b01d33aa A    runtime/syntax/json5.vim
        :100644 100644 671b269c0 ef52cddf4 M    runtime/syntax/nix.vim
        :100644 100644 69671c59c 084f8cdb4 M    runtime/syntax/zsh.vim
        :100644 100644 b90f76fc1 bad07e644 R099 src/version.c   src/version2.c
        :100644 000000 b5825eb19 000000000 D    src/testdir/dumps

        ':100644 100644 72943a1 dbee026 R050\thello world.txt\thello world2.txt'

        return a tuple like (100644, (b90f76fc1, bad07e644, R099, src/version.c, src/version2.c))
                            (100644, (69671c59c, 084f8cdb4, M,    runtime/syntax/zsh.vim, ""))
        """
        tmp = line.split(sep='\t')
        file_names = (tmp[1], tmp[2] if len(tmp) == 3 else "")
        blob_status = tmp[0].split()
        return (blob_status[1],
                (blob_status[2], blob_status[3], blob_status[4],
                file_names[0], file_names[1])
                )

    def buildFileStructure(self, level, name, tree_node, path):
        if tree_node.status == FolderStatus.CLOSED:
            return

        if len(tree_node.dirs) == 1 and len(tree_node.files) == 0:
            dir_name, node = tree_node.dirs.last_key_value()
            self.buildFileStructure(level, "{}/{}".format(name, dir_name),
                                    node, "{}{}/".format(path, dir_name)
                                    )
        else:
            self._file_structures[self._current_parent].append(
                    MetaInfo(level, True, name, tree_node, path)
                    )

            for dir_name, node in tree_node.dirs.items():
                self.buildFileStructure(level + 1, dir_name, node,
                                        "{}{}/".format(path, dir_name))

            self.appendFiles(level + 1, tree_node)

    def appendRemainingFiles(self, tree_node):
        if tree_node.status == FolderStatus.CLOSED:
            return

        dir_name, node = tree_node.dirs.last_key_value()
        if len(node.dirs) > 1:
            child_dir_name, child_node = node.dirs.last_key_value()
            self.buildFileStructure(1, child_dir_name, child_node,
                                    "{}/{}/".format(dir_name, child_dir_name))

            self.appendFiles(1, node)
        else:
            self.buildFileStructure(0, dir_name, node, dir_name + "/")

    def appendFiles(self, level, tree_node):
        if tree_node.status == FolderStatus.CLOSED:
            return

        for k, v in tree_node.files.items():
            self._file_structures[self._current_parent].append(
                    MetaInfo(level, False, k, v,
                             v[3] if v[4] == "" else v[4])
                    )

    def buildTree(self, line):
        """
        command output is something as follows:

        # 9d0ccb54c743424109751a82a742984699e365fe 63aa0c07bcd16ddac52d5275b9513712b780bc25
        :100644 100644 0cbabf4 d641678 M        src/a.txt
        2       0       src/a.txt
         1 file changed, 2 insertions(+)

        # 9d0ccb54c743424109751a82a742984699e365fe 63aa0c07bcd16ddac52d5275b9513712b780bc25
        :100644 100644 acc5824 d641678 M        src/a.txt
        3       0       src/a.txt
         1 file changed, 3 insertions(+)
        """
        if line.startswith("#"):
            size = len(self._trees)
            parents = line.split()
            if len(parents) == 1: # first commit
                parent = "0000000"
            else:
                parent = parents[size + 1]
            if self._current_parent is None:
                self._current_parent = parent
            self._trees[parent] = TreeNode()
            self._file_structures[parent] = []
        elif line.startswith(":"):
            mode, source = self.generateSource(line)
            file_path = source[3] if source[4] == "" else source[4]
            tree_node = self._trees.last_value()
            if mode == "160000": # gitlink
                directories = file_path.split("/")
            else:
                *directories, file = file_path.split("/")
            with self._lock:
                for i, d in enumerate(directories, 0):
                    if i == 0:
                        level0_dir_name = d

                    if d not in tree_node.dirs:
                        # not first directory
                        if len(tree_node.dirs) > 0:
                            if i == 1:
                                if len(tree_node.dirs) == 1:
                                    self._file_structures[self._current_parent].append(
                                            MetaInfo(0, True, level0_dir_name,
                                                     tree_node, level0_dir_name + "/")
                                            )

                                dir_name, node = tree_node.dirs.last_key_value()
                                self.buildFileStructure(1, dir_name, node,
                                                        "{}/{}/".format(level0_dir_name, dir_name))
                            elif i == 0:
                                self.appendRemainingFiles(tree_node)

                        if len(self._file_structures[self._current_parent]) >= self._preopen_num:
                            status = FolderStatus.CLOSED
                        else:
                            status = FolderStatus.OPEN
                        tree_node.dirs[d] = TreeNode(status)

                    tree_node = tree_node.dirs[d]

            if mode != "160000":
                tree_node.files[file] = source
        elif line.startswith(" "):
            parent, tree_node = self._trees.last_key_value()
            self._short_stat[parent] = line
            self.appendRemainingFiles(tree_node)
            self.appendFiles(0, tree_node)
        elif line == "":
            pass
        else:
            parent = self._trees.last_key()
            if parent not in self._num_stat:
                self._num_stat[parent] = {}

            #'3\t1\tarch/{i386 => x86}/Makefile'
            added, deleted, pathname = line.split("\t")
            if "=>" in pathname:
                if "{" in pathname:
                    pathname = re.sub(r'{.*?=> (.*?)}', r'\1', pathname)
                else:
                    pathname = pathname.split(" => ")[1]
            if added == "-" and deleted == "-":
                self._num_stat[parent][pathname] = "(Bin)"
            else:
                self._num_stat[parent][pathname] = "+{:3} -{}".format(added, deleted)

    def metaInfoGenerator(self, meta_info, tree_node, recursive):
        meta_info.info.status = FolderStatus.OPEN

        if len(tree_node.dirs) == 1 and len(tree_node.files) == 0:
            dir_name, node = tree_node.dirs.last_key_value()
            meta_info.name = "{}/{}".format(meta_info.name, dir_name)
            meta_info.path = "{}{}/".format(meta_info.path, dir_name)
            yield from self.metaInfoGenerator(meta_info, node, recursive)
            return

        for dir_name, node in tree_node.dirs.items():
            cur_path = "{}{}/".format(meta_info.path, dir_name)
            info = MetaInfo(meta_info.level + 1, True, dir_name, node, cur_path)
            yield info
            if recursive == True or node.status == FolderStatus.OPEN:
                yield from self.metaInfoGenerator(info, node, recursive)

        for k, v in tree_node.files.items():
            yield MetaInfo(meta_info.level + 1, False, k, v, v[3] if v[4] == "" else v[4])

    def expandOrCollapseFolder(self, recursive=False):
        with self._lock:
            line_num = vim.current.window.cursor[0]
            index = line_num - len(self._head) - 1
            structure = self._file_structures[self._current_parent]
            if index < 0 or index >= len(structure):
                return

            meta_info = structure[index]
            if meta_info.is_dir:
                if meta_info.info.status == FolderStatus.CLOSED:
                    self.expandFolder(line_num, index, meta_info, meta_info.info, recursive)
                else:
                    pass
            else:
                pass

    def expandFolder(self, line_num, index, meta_info, tree_node, recursive):
        structure = self._file_structures[self._current_parent]
        size = len(structure)
        structure[index + 1 : index + 1] = self.metaInfoGenerator(meta_info, tree_node, recursive)
        self._buffer.options['modifiable'] = True
        try:
            increment = len(structure) - size
            self._buffer[line_num - 1] = self.buildLine(structure[index])
            self._buffer.append([self.buildLine(info)
                                 for info in structure[index + 1 : index + 1 + increment]],
                                line_num)
            self._offset_in_content += increment
        finally:
            self._buffer.options['modifiable'] = False

    def collapseFolder(self, index):
        pass

    def findFile(self, path):
        pass

    def buildLine(self, info):
        """
        info is MetaInfo
        """
        if info.is_dir:
            if info.info.status == FolderStatus.CLOSED:
                icon = self._closed_folder_icon
            else:
                icon = self._open_folder_icon
            return "{}{} {}/".format("  " * info.level, icon, info.name)
        else:
            num_stat = self._num_stat.get(self._current_parent, {}).get(info.path, "")
            icon = self._status_icons.get(info.info[2][0], self._modification_icon)

            orig_name = ""
            if info.info[2][0] in ("R", "C"):
                head, tail = os.path.split(info.info[3])
                orig_name = "{} => ".format(os.path.relpath(info.info[3], os.path.dirname(info.info[4])))

            return "{}{} {}{}\t{}".format("  " * info.level,
                                          icon,
                                          orig_name,
                                          info.name,
                                          num_stat
                                          )

    def setOptions(self, bufhidden):
        super(TreeView, self).setOptions(bufhidden)
        lfCmd(r"call win_execute({}, 'setlocal stl=\ {}')".format(self._window_id, self._project_root + "/"))
        lfCmd("call win_execute({}, 'setlocal cursorline')".format(self._window_id))
        lfCmd("call win_execute({}, 'noautocmd setlocal sw=2 tabstop=8')".format(self._window_id))
        lfCmd("call win_execute({}, 'setlocal signcolumn=no')".format(self._window_id))
        try:
            lfCmd(r"call win_execute({}, 'setlocal list lcs=leadmultispace:¦\ ,tab:\ \ ')"
                  .format(self._window_id))
        except vim.error:
            lfCmd("call win_execute({}, 'setlocal nolist')".format(self._window_id))

    def initBuffer(self):
        self._buffer.options['modifiable'] = True
        try:
            self._buffer[:] = self._head
        finally:
            self._buffer.options['modifiable'] = False

    def writeBuffer(self):
        if self._current_parent is None:
            return

        if self._read_finished == 2:
            return

        if not self._buffer.valid:
            self.stopTimer()
            return

        with self._lock:
            self._buffer.options['modifiable'] = True
            try:
                structure = self._file_structures[self._current_parent]
                cur_len = len(structure)
                if cur_len > self._offset_in_content:
                    self._buffer.append([self.buildLine(info)
                                         for info in structure[self._offset_in_content:cur_len]])

                    self._offset_in_content = cur_len
                    lfCmd("redraw")
            finally:
                self._buffer.options['modifiable'] = False

        if self._read_finished == 1 and self._offset_in_content == len(structure):
            self._read_finished = 2
            self._owner.writeFinished(self._window_id)
            self.stopTimer()

    def _readContent(self, content):
        try:
            for line in content:
                self.buildTree(line)
                if self._stop_reader_thread:
                    break
            else:
                self._read_finished = 1
                self._owner.readFinished(self)
        except Exception as e:
            self._read_finished = 1
            print(e)

    def cleanup(self):
        super(TreeView, self).cleanup()
        lfCmd("bwipe {}".format(self._buffer.number))

        self._match_ids = []


class Panel(object):
    def __init__(self):
        pass

    def register(self, view):
        pass

    def deregister(self, view):
        pass

    def cleanup(self):
        pass

    def writeBuffer(self):
        pass

    def readFinished(self, view):
        pass

    def writeFinished(self, winid):
        pass


class ResultPanel(Panel):
    def __init__(self):
        self._views = {}
        self._sources = set()

    def register(self, view):
        self._views[view.getBufferName()] = view
        self._sources.add(view.getSource())

    def deregister(self, view):
        name = view.getBufferName()
        if name in self._views:
            self._sources.discard(self._views[name].getSource())
            self._views[name].cleanup()
            del self._views[name]

    def getSources(self):
        return self._sources

    def _createWindow(self, win_pos, buffer_name):
        if win_pos == 'top':
            lfCmd("silent! noa keepa keepj abo sp {}".format(buffer_name))
        elif win_pos == 'bottom':
            lfCmd("silent! noa keepa keepj bel sp {}".format(buffer_name))
        elif win_pos == 'left':
            lfCmd("silent! noa keepa keepj abo vsp {}".format(buffer_name))
        elif win_pos == 'right':
            lfCmd("silent! noa keepa keepj bel vsp {}".format(buffer_name))
        else:
            lfCmd("silent! keepa keepj hide edit {}".format(buffer_name))

        return int(lfEval("win_getid()"))

    def create(self, cmd, content=None):
        buffer_name = cmd.getBufferName()
        if buffer_name in self._views and self._views[buffer_name].valid():
            self._views[buffer_name].create(buf_content=content)
        else:
            winid = self._createWindow(cmd.getArguments().get("--position", [""])[0], buffer_name)
            GitCommandView(self, cmd, winid).create(buf_content=content)

    def writeBuffer(self):
        for v in self._views.values():
            v.writeBuffer()


class PreviewPanel(Panel):
    def __init__(self):
        self._view = None
        self._buffer_contents = {}
        self._preview_winid = 0

    def register(self, view):
        if self._view is not None:
            self._view.cleanup()
        self._view = view

    def deregister(self, view):
        if self._view is view:
            self._view.cleanup()
            self._view = None

    def create(self, cmd, config):
        if lfEval("has('nvim')") == '1':
            lfCmd("noautocmd let scratch_buffer = nvim_create_buf(0, 1)")
            self._preview_winid = int(lfEval("nvim_open_win(scratch_buffer, 0, %s)" % json.dumps(config)))
        else:
            lfCmd("noautocmd silent! let winid = popup_create([], %s)" % json.dumps(config))
            self._preview_winid = int(lfEval("winid"))

        GitCommandView(self, cmd, self._preview_winid).create()

    def createView(self, cmd):
        if self._preview_winid > 0:
            GitCommandView(self, cmd, self._preview_winid).create()

    def writeBuffer(self):
        if self._view is not None:
            self._view.writeBuffer()

    def getPreviewWinId(self):
        return self._preview_winid

    def cleanup(self):
        if self._view is not None:
            # may never run here
            self._view.cleanup()
        self._view = None
        self._buffer_contents = {}
        self._preview_winid = 0

    def readFinished(self, view):
        self._buffer_contents[view.getSource()] = view.getContent()

    def getContent(self, source):
        return self._buffer_contents.get(source)

    def setContent(self, content):
        if self._view:
            self._view.setContent(content)


class SplitDiffPanel(Panel):
    def __init__(self):
        self._views = {}
        self._buffer_contents = {}

    def register(self, view):
        self._views[view.getBufferName()] = view

    def deregister(self, view):
        name = view.getBufferName()
        if name in self._views:
            self._views[name].cleanup()
            del self._views[name]

    def cleanup(self):
        self._buffer_contents = {}

    def readFinished(self, view):
        self._buffer_contents[view.getSource()] = view.getContent()

    def getContent(self, source):
        return self._buffer_contents.get(source)

    def writeFinished(self, winid):
        lfCmd("call win_execute({}, 'diffthis')".format(winid))

    def create(self, arguments_dict, source, **kwargs):
        """
        source is a tuple like (b90f76fc1, bad07e644, R099, src/version.c, src/version2.c)
        """
        file_name = source[4] if source[4] != "" else source[3]
        sources = ((source[0], source[2], source[3]),
                   (source[1], source[2], file_name))
        buffer_names = (GitCatFileCommand.buildBufferName(sources[0]),
                        GitCatFileCommand.buildBufferName(sources[1]))
        if buffer_names[0] in self._views and buffer_names[1] in self._views:
            win_ids = (self._views[buffer_names[0]].getWindowId(),
                       self._views[buffer_names[1]].getWindowId())
            lfCmd("call win_gotoid({})".format(win_ids[0]))
        elif buffer_names[0] in self._views:
            lfCmd("call win_gotoid({})".format(self._views[buffer_names[0]].getWindowId()))
            cmd = GitCatFileCommand(arguments_dict, sources[1])
            lfCmd("rightbelow vsp {}".format(cmd.getBufferName()))
            GitCommandView(self, cmd, int(lfEval("win_getid()"))).create(buf_content=self.getContent(sources[1]))
            lfCmd("call win_gotoid({})".format(self._views[buffer_names[0]].getWindowId()))
        elif buffer_names[1] in self._views:
            lfCmd("call win_gotoid({})".format(self._views[buffer_names[1]].getWindowId()))
            cmd = GitCatFileCommand(arguments_dict, sources[0])
            lfCmd("leftabove vsp {}".format(cmd.getBufferName()))
            GitCommandView(self, cmd, int(lfEval("win_getid()"))).create(buf_content=self.getContent(sources[0]))
        else:
            if kwargs.get("mode", '') == 't':
                lfCmd("noautocmd tabnew | vsp")
                tabmove()
                win_ids = [int(lfEval("win_getid({})".format(w.number)))
                           for w in vim.current.tabpage.windows]
            else:
                wins = vim.current.tabpage.windows
                if (len(wins) == 2
                    and lfEval("bufname({}+0)".format(wins[0].buffer.number)) in self._views
                    and lfEval("bufname({}+0)".format(wins[1].buffer.number)) in self._views):
                    win_ids = [int(lfEval("win_getid({})".format(w.number)))
                               for w in vim.current.tabpage.windows]
                else:
                    lfCmd("noautocmd tabnew | vsp")
                    tabmove()
                    win_ids = [int(lfEval("win_getid({})".format(w.number)))
                               for w in vim.current.tabpage.windows]

            cat_file_cmds = [GitCatFileCommand(arguments_dict, s) for s in sources]
            outputs = [self.getContent(s) for s in sources]
            if None in outputs:
                outputs = ParallelExecutor.run(*cat_file_cmds)

            for i, (cmd, winid) in enumerate(zip(cat_file_cmds, win_ids)):
                lfCmd("call win_execute({}, 'edit {}')".format(winid, cmd.getBufferName()))
                GitCommandView(self, cmd, winid).create(buf_content=outputs[i])


class NavigationPanel(Panel):
    def __init__(self):
        self._tree_view = None

    def register(self, view):
        self._tree_view = view

    def cleanup(self):
        if self._tree_view is not None:
            self._tree_view.cleanup()
            self._tree_view = None

    def create(self, cmd, winid, project_root):
        TreeView(self, cmd, winid, project_root).create(bufhidden="hide")

    def writeBuffer(self):
        # called in idle
        if self._tree_view is not None:
            self._tree_view.writeBuffer()


class DiffViewPanel(Panel):
    def __init__(self):
        pass


class ExplorerPage(object):
    def __init__(self, project_root):
        self._project_root = project_root
        self._navigation_panel = None
        self._diff_view_panel = None
        self.tabpage = None

    def _createWindow(self, win_pos, buffer_name):
        if win_pos == 'top':
            lfCmd("silent! noa keepa keepj abo sp {}".format(buffer_name))
        elif win_pos == 'bottom':
            lfCmd("silent! noa keepa keepj bel sp {}".format(buffer_name))
        elif win_pos == 'left':
            lfCmd("silent! noa keepa keepj abo vsp {}".format(buffer_name))
        elif win_pos == 'right':
            lfCmd("silent! noa keepa keepj bel vsp {}".format(buffer_name))
        else:
            lfCmd("silent! noa keepa keepj abo vsp {}".format(buffer_name))

        return int(lfEval("win_getid()"))

    def create(self, arguments_dict, source):
        lfCmd("noautocmd tabnew")
        self.tabpage = vim.current.tabpage

        cmd = GitLogExplCommand(arguments_dict, source)
        win_pos = arguments_dict.get("--navigation-position", [""])[0]
        winid = self._createWindow(win_pos, cmd.getBufferName())

        self._navigation_panel = NavigationPanel()
        self._navigation_panel.create(cmd, winid, self._project_root)

    def cleanup(self):
        if self._navigation_panel is not None:
            self._navigation_panel.cleanup()

        if self._diff_view_panel is not None:
            self._diff_view_panel.cleanup()


#*****************************************************
# GitExplManager
#*****************************************************
class GitExplManager(Manager):
    def __init__(self):
        super(GitExplManager, self).__init__()
        self._show_icon = lfEval("get(g:, 'Lf_ShowDevIcons', 1)") == "1"
        self._result_panel = ResultPanel()
        self._preview_panel = PreviewPanel()
        self._git_diff_manager = None
        self._git_log_manager = None
        self._selected_content = None
        self._project_root = ""

    def _getExplClass(self):
        return GitExplorer

    def _defineMaps(self):
        lfCmd("call leaderf#Git#Maps({})".format(id(self)))
        if type(self) is GitExplManager:
            lfCmd("call leaderf#Git#SpecificMaps({})".format(id(self)))

    def _createHelp(self):
        help = []
        help.append('" <CR>/<double-click>/o : execute command under cursor')
        help.append('" i/<Tab> : switch to input mode')
        if type(self) is GitExplManager:
            help.append('" e : edit command under cursor')
        help.append('" p : preview the help information')
        help.append('" q : quit')
        help.append('" <F1> : toggle this help')
        help.append('" <ESC> : close the preview window or quit')
        help.append('" ---------------------------------------------------------')
        return help

    def _workInIdle(self, content=None, bang=False):
        self._result_panel.writeBuffer()
        self._preview_panel.writeBuffer()

        super(GitExplManager, self)._workInIdle(content, bang)

    def _beforeExit(self):
        super(GitExplManager, self)._beforeExit()
        self._preview_panel.cleanup()

    def getExplManager(self, subcommand):
        if subcommand == "diff":
            if self._git_diff_manager is None:
                self._git_diff_manager = GitDiffExplManager()
            return self._git_diff_manager
        elif subcommand == "log":
            if self._git_log_manager is None:
                self._git_log_manager = GitLogExplManager()
            return self._git_log_manager
        else:
            return super(GitExplManager, self)

    def checkWorkingDirectory(self):
        self._orig_cwd = lfGetCwd()
        self._project_root = nearestAncestor([".git"], self._orig_cwd)
        if self._project_root: # there exists a root marker in nearest ancestor path
            # https://github.com/neovim/neovim/issues/8336
            if lfEval("has('nvim')") == '1':
                chdir = vim.chdir
            else:
                chdir = os.chdir
            chdir(self._project_root)
        else:
            lfPrintError("Not a git repository (or any of the parent directories): .git")
            return False

        return True

    def startExplorer(self, win_pos, *args, **kwargs):
        arguments_dict = kwargs.get("arguments", {})
        if "--recall" in arguments_dict:
            self._arguments.update(arguments_dict)
        else:
            self.setArguments(arguments_dict)

        arg_list = self._arguments.get("arg_line", 'git').split()
        arg_list = [item for item in arg_list if not item.startswith('-')]
        if len(arg_list) == 1:
            subcommand = ""
        else:
            subcommand = arg_list[1]
        self.getExplManager(subcommand).startExplorer(win_pos, *args, **kwargs)

    def accept(self, mode=''):
        source = self.getSource(self._getInstance().currentLine)
        self._selected_content = self._preview_panel.getContent(source)

        return super(GitExplManager, self).accept(mode)

    def _accept(self, file, mode, *args, **kwargs):
        self._acceptSelection(file, *args, **kwargs)

    def _acceptSelection(self, *args, **kwargs):
        if len(args) == 0:
            return

        line = args[0]
        cmd = line
        try:
            lfCmd(cmd)
        except vim.error:
            lfPrintTraceback()

    def _bangEnter(self):
        super(GitExplManager, self)._bangEnter()

        if lfEval("exists('*timer_start')") == '0':
            lfCmd("echohl Error | redraw | echo ' E117: Unknown function: timer_start' | echohl NONE")
            return

        self._callback(bang=True)
        if self._read_finished < 2:
            self._timer_id = lfEval("timer_start(10, function('leaderf#Git#TimerCallback', [%d]), {'repeat': -1})" % id(self))

    def getSource(self, line):
        commands = lfEval("leaderf#Git#Commands()")
        for cmd in commands:
            if line in cmd:
                return cmd[line]

        return None

    def _previewInPopup(self, *args, **kwargs):
        if len(args) == 0 or args[0] == '':
            return

        line = args[0]
        source = self.getSource(line)

        self._createPopupPreview("", source, 0)

    def _createPreviewWindow(self, config, source, line_num, jump_cmd):
        if lfEval("has('nvim')") == '1':
            lfCmd("noautocmd let scratch_buffer = nvim_create_buf(0, 1)")
            lfCmd("noautocmd call setbufline(scratch_buffer, 1, '{}')".format(escQuote(source)))
            lfCmd("noautocmd call nvim_buf_set_option(scratch_buffer, 'bufhidden', 'wipe')")
            lfCmd("noautocmd call nvim_buf_set_option(scratch_buffer, 'undolevels', -1)")

            self._preview_winid = int(lfEval("nvim_open_win(scratch_buffer, 0, {})".format(json.dumps(config))))
        else:
            lfCmd("noautocmd let winid = popup_create('{}', {})".format(escQuote(source), json.dumps(config)))
            self._preview_winid = int(lfEval("winid"))

        self._setWinOptions(self._preview_winid)

    def createGitCommand(self, arguments_dict, source):
        pass

    def _useExistingWindow(self, title, source, line_num, jump_cmd):
        self.setOptionsForCursor()

        if lfEval("has('nvim')") == '1':
            lfCmd("""call win_execute({}, "call nvim_buf_set_lines(0, 0, -1, v:false, ['{}'])")"""
                  .format(self._preview_winid, escQuote(source)))
        else:
            lfCmd("noautocmd call popup_settext({}, '{}')".format(self._preview_winid, escQuote(source)))

    def _cmdExtension(self, cmd):
        if type(self) is GitExplManager:
            if equal(cmd, '<C-o>'):
                self.editCommand()
            return True

    def editCommand(self):
        instance = self._getInstance()
        line = instance.currentLine
        instance.exitBuffer()
        lfCmd("call feedkeys(':%s', 'n')" % escQuote(line))


class GitDiffExplManager(GitExplManager):
    def __init__(self):
        super(GitDiffExplManager, self).__init__()
        self._split_diff_panel = SplitDiffPanel()

    def _getExplorer(self):
        if self._explorer is None:
            self._explorer = GitDiffExplorer()
        return self._explorer

    def getSource(self, line):
        """
        return a tuple like (b90f76fc1, bad07e644, R099, src/version.c, src/version2.c)
        """
        file_name2 = ""
        if "\t->\t" in line:
            # 'R050 hello world.txt\t->\thello world2.txt'
            # 'R050   hello world.txt\t->\thello world2.txt'
            tmp = line.split("\t->\t")
            file_name1 = tmp[0].split(None, 2 if self._show_icon else 1)[-1]
            file_name2 = tmp[1]
        else:
            # 'M      runtime/syntax/nix.vim'
            file_name1 = line.split()[-1]

        return self._getExplorer().getSourceInfo()[(file_name1, file_name2)]

    def _createPreviewWindow(self, config, source, line_num, jump_cmd):
        self._preview_panel.create(self.createGitCommand(self._arguments, source), config)
        self._preview_winid = self._preview_panel.getPreviewWinId()
        self._setWinOptions(self._preview_winid)

    def createGitCommand(self, arguments_dict, source):
        return GitDiffCommand(arguments_dict, source)

    def _useExistingWindow(self, title, source, line_num, jump_cmd):
        self.setOptionsForCursor()

        content = self._preview_panel.getContent(source)
        if content is None:
            self._preview_panel.createView(self.createGitCommand(self._arguments, source))
        else:
            self._preview_panel.setContent(content)

    def startExplorer(self, win_pos, *args, **kwargs):
        if self.checkWorkingDirectory() == False:
            return

        arguments_dict = kwargs.get("arguments", {})
        if "--recall" not in arguments_dict:
            self.setArguments(arguments_dict)

        if "--recall" in arguments_dict:
            super(GitExplManager, self).startExplorer(win_pos, *args, **kwargs)
        elif "--directly" in self._arguments:
            self._result_panel.create(self.createGitCommand(self._arguments, None))
            self._restoreOrigCwd()
        elif "--explorer" in self._arguments:
            pass
        else:
            # cleanup the cache when starting
            self._split_diff_panel.cleanup()
            super(GitExplManager, self).startExplorer(win_pos, *args, **kwargs)

    def _afterEnter(self):
        super(GitExplManager, self)._afterEnter()

        if lfEval("get(g:, 'Lf_ShowDevIcons', 1)") == '1':
            winid = self._getInstance().getPopupWinId() if self._getInstance().getWinPos() == 'popup' else None
            icon_pattern = r'^\S*\s*\zs__icon__'
            self._match_ids.extend(matchaddDevIconsExtension(icon_pattern, winid))
            self._match_ids.extend(matchaddDevIconsExact(icon_pattern, winid))
            self._match_ids.extend(matchaddDevIconsDefault(icon_pattern, winid))

        if self._getInstance().getWinPos() == 'popup':
            lfCmd(r"""call win_execute(%d, 'let matchid = matchadd(''Lf_hl_gitDiffModification'', ''^[MRT]\S*'')')"""
                    % self._getInstance().getPopupWinId())
            id = int(lfEval("matchid"))
            lfCmd(r"""call win_execute(%d, 'let matchid = matchadd(''Lf_hl_gitDiffAddition'', ''^[AC]\S*'')')"""
                    % self._getInstance().getPopupWinId())
            id = int(lfEval("matchid"))
            lfCmd(r"""call win_execute(%d, 'let matchid = matchadd(''Lf_hl_gitDiffDeletion'', ''^[DU]'')')"""
                    % self._getInstance().getPopupWinId())
            id = int(lfEval("matchid"))
        else:
            id = int(lfEval(r'''matchadd('Lf_hl_gitDiffModification', '^[MRT]\S*')'''))
            self._match_ids.append(id)
            id = int(lfEval(r'''matchadd('Lf_hl_gitDiffAddition', '^[AC]\S*')'''))
            self._match_ids.append(id)
            id = int(lfEval(r'''matchadd('Lf_hl_gitDiffDeletion', '^[DU]')'''))
            self._match_ids.append(id)

    def _accept(self, file, mode, *args, **kwargs):
        if "-s" in self._arguments:
            kwargs["mode"] = mode
            self._acceptSelection(file, *args, **kwargs)
        else:
            super(GitExplManager, self)._accept(file, mode, *args, **kwargs)

    def _acceptSelection(self, *args, **kwargs):
        if len(args) == 0:
            return

        line = args[0]
        source = self.getSource(line)

        if "-s" in self._arguments:
            self._split_diff_panel.create(self._arguments, source, **kwargs)
        else:
            if kwargs.get("mode", '') == 't' and source not in self._result_panel.getSources():
                lfCmd("tabnew")

            tabpage_count = len(vim.tabpages)

            self._result_panel.create(self.createGitCommand(self._arguments, source), self._selected_content)

            if kwargs.get("mode", '') == 't' and len(vim.tabpages) > tabpage_count:
                tabmove()


class GitLogExplManager(GitExplManager):
    def __init__(self):
        super(GitLogExplManager, self).__init__()
        # key is source, value is ExplorerPage
        self._pages = {}

    def _getExplorer(self):
        if self._explorer is None:
            self._explorer = GitLogExplorer()
        return self._explorer

    def getSource(self, line):
        """
        return the hash
        """
        return line.split(None, 1)[0]

    def _createPreviewWindow(self, config, source, line_num, jump_cmd):
        self._preview_panel.create(self.createGitCommand(self._arguments, source), config)
        self._preview_winid = self._preview_panel.getPreviewWinId()
        self._setWinOptions(self._preview_winid)

    def createGitCommand(self, arguments_dict, source):
        return GitLogCommand(arguments_dict, source)

    def _useExistingWindow(self, title, source, line_num, jump_cmd):
        self.setOptionsForCursor()

        content = self._preview_panel.getContent(source)
        if content is None:
            self._preview_panel.createView(self.createGitCommand(self._arguments, source))
        else:
            self._preview_panel.setContent(content)

    def startExplorer(self, win_pos, *args, **kwargs):
        if self.checkWorkingDirectory() == False:
            return

        arguments_dict = kwargs.get("arguments", {})
        if "--recall" not in arguments_dict:
            self.setArguments(arguments_dict)

        if "--recall" in arguments_dict:
            super(GitExplManager, self).startExplorer(win_pos, *args, **kwargs)
        elif "--directly" in self._arguments:
            self._result_panel.create(self.createGitCommand(self._arguments, None))
            self._restoreOrigCwd()
        else:
            super(GitExplManager, self).startExplorer(win_pos, *args, **kwargs)

    def _afterEnter(self):
        super(GitExplManager, self)._afterEnter()

        if self._getInstance().getWinPos() == 'popup':
            lfCmd(r"""call win_execute(%d, 'let matchid = matchadd(''Lf_hl_gitHash'', ''^[0-9A-Fa-f]\+'')')"""
                    % self._getInstance().getPopupWinId())
            id = int(lfEval("matchid"))
            lfCmd(r"""call win_execute(%d, 'let matchid = matchadd(''Lf_hl_gitRefNames'', ''^[0-9A-Fa-f]\+\s*\zs(.\{-})'')')"""
                    % self._getInstance().getPopupWinId())
            id = int(lfEval("matchid"))
        else:
            id = int(lfEval(r'''matchadd('Lf_hl_gitHash', '^[0-9A-Fa-f]\+')'''))
            self._match_ids.append(id)
            id = int(lfEval(r'''matchadd('Lf_hl_gitRefNames', '^[0-9A-Fa-f]\+\s*\zs(.\{-})')'''))
            self._match_ids.append(id)

    def _accept(self, file, mode, *args, **kwargs):
        super(GitExplManager, self)._accept(file, mode, *args, **kwargs)

    def _acceptSelection(self, *args, **kwargs):
        if len(args) == 0:
            return

        line = args[0]
        source = self.getSource(line)

        if "--explorer" in self._arguments:
            if source in self._pages:
                vim.current.tabpage = self._pages[source].tabpage
            else:
                lfCmd("augroup Lf_Git | augroup END")
                lfCmd("autocmd! Lf_Git TabClosed * call leaderf#Git#CleanupExplorerPage({})"
                      .format(id(self)))

                self._pages[source] = ExplorerPage(self._project_root)
                self._pages[source].create(self._arguments, source)
        else:
            if kwargs.get("mode", '') == 't' and source not in self._result_panel.getSources():
                lfCmd("tabnew")

            tabpage_count = len(vim.tabpages)

            self._result_panel.create(self.createGitCommand(self._arguments, source), self._selected_content)

            if kwargs.get("mode", '') == 't' and len(vim.tabpages) > tabpage_count:
                tabmove()

    def cleanup(self):
        for k, v in self._pages.items():
            if v.tabpage not in vim.tabpages:
                v.cleanup()
                del self._pages[k]
                return

#*****************************************************
# gitExplManager is a singleton
#*****************************************************
gitExplManager = GitExplManager()

__all__ = ['gitExplManager']
