" ============================================================================
" File:        Git.vim
" Description:
" Author:      Yggdroot <archofortune@gmail.com>
" Website:     https://github.com/Yggdroot
" Note:
" License:     Apache License, Version 2.0
" ============================================================================

if leaderf#versionCheck() == 0  " this check is necessary
    finish
endif

exec g:Lf_py "from leaderf.gitExpl import *"

function! leaderf#Git#Maps(id)
    nmapclear <buffer>
    exec g:Lf_py "import ctypes"
    let manager = printf("ctypes.cast(%d, ctypes.py_object).value", a:id)
    exec printf('nnoremap <buffer> <silent> <CR>          :exec g:Lf_py "%s.accept()"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> o             :exec g:Lf_py "%s.accept()"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> <2-LeftMouse> :exec g:Lf_py "%s.accept()"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> x             :exec g:Lf_py "%s.accept(''h'')"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> v             :exec g:Lf_py "%s.accept(''v'')"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> t             :exec g:Lf_py "%s.accept(''t'')"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> p             :exec g:Lf_py "%s._previewResult(True)"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> j             :exec g:Lf_py "%s.moveAndPreview(''j'')"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> k             :exec g:Lf_py "%s.moveAndPreview(''k'')"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> <Up>          :exec g:Lf_py "%s.moveAndPreview(''Up'')"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> <Down>        :exec g:Lf_py "%s.moveAndPreview(''Down'')"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> <PageUp>      :exec g:Lf_py "%s.moveAndPreview(''PageUp'')"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> <PageDown>    :exec g:Lf_py "%s.moveAndPreview(''PageDown'')"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> q             :exec g:Lf_py "%s.quit()"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> i             :exec g:Lf_py "%s.input()"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> <Tab>         :exec g:Lf_py "%s.input()"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> <F1>          :exec g:Lf_py "%s.toggleHelp()"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> <C-Up>        :exec g:Lf_py "%s._toUpInPopup()"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> <C-Down>      :exec g:Lf_py "%s._toDownInPopup()"<CR>', manager)
    exec printf('nnoremap <buffer> <silent> <Esc>         :exec g:Lf_py "%s.closePreviewPopupOrQuit()"<CR>', manager)
endfunction

" direction:
"   0, backward
"   1, forward
function! leaderf#Git#OuterIndent(direction)
    let spaces = substitute(getline('.'), '^\(\s*\).*', '\1', '')
    let width = strdisplaywidth(spaces)
    if width == 0
        return 0
    endif
    if a:direction == 0
        let flags = 'sbW'
    else
        let flags = 'sW'
    endif
    return search(printf('^\s\{,%d}\zs\S', width-1), flags)
endfunction

" direction:
"   0, backward
"   1, forward
function! leaderf#Git#SameIndent(direction)
    let spaces = substitute(getline('.'), '^\(\s*\).*', '\1', '')
    let width = strdisplaywidth(spaces)
    if a:direction == 0
        let flags = 'sbW'
    else
        let flags = 'sW'
    endif
    if width == 0
        let stopline = 0
    else
        let stopline = search(printf('^\s\{,%d}\zs\S', width-1), flags[1:].'n')
    endif

    noautocmd norm! ^
    call search(printf('^\s\{%d}\zs\S', width), flags, stopline)
endfunction

function! leaderf#Git#SpecificMaps(id)
    exec g:Lf_py "import ctypes"
    let manager = printf("ctypes.cast(%d, ctypes.py_object).value", a:id)
    exec printf('nnoremap <buffer> <silent> e :exec g:Lf_py "%s.editCommand()"<CR>', manager)
endfunction

" direction:
"   0, backward
"   1, forward
function! leaderf#Git#OuterBlock(direction)
    let column = col('.')
    if column >= match(getline('.'), '\S') + 1
        noautocmd norm! ^
        let column = col('.') - 1
    endif
    let width = (column - 1) / 2 * 2
    if a:direction == 0
        let flags = 'sbW'
    else
        let flags = 'sW'
    endif
    call search(printf('^\s\{%d}\zs\S', width), flags)
endfunction

function! leaderf#Git#TreeViewMaps(id)
    exec g:Lf_py "import ctypes"
    let tree_view = printf("ctypes.cast(%d, ctypes.py_object).value", a:id)
    exec printf('nnoremap <silent> X         :exec g:Lf_py "%s.collapseChildren()"<CR>', tree_view)
    nnoremap <buffer> <silent> -             :call leaderf#Git#OuterIndent(0)<CR>
    nnoremap <buffer> <silent> +             :call leaderf#Git#OuterIndent(1)<CR>
    nnoremap <buffer> <silent> <C-K>         :call leaderf#Git#SameIndent(0)<CR>
    nnoremap <buffer> <silent> <C-J>         :call leaderf#Git#SameIndent(1)<CR>
    nnoremap <buffer> <silent> (             :call leaderf#Git#OuterBlock(0)<CR>
    nnoremap <buffer> <silent> )             :call leaderf#Git#OuterBlock(1)<CR>
endfunction

function! leaderf#Git#CollapseParent(explorer_page)
    if leaderf#Git#OuterIndent(0) != 0
        exec g:Lf_py printf("%s.open(False)", a:explorer_page)
    endif
endfunction

function! leaderf#Git#ExplorerMaps(id)
    exec g:Lf_py "import ctypes"
    let explorer_page = printf("ctypes.cast(%d, ctypes.py_object).value", a:id)
    exec printf('nnoremap <buffer> <silent> o             :exec g:Lf_py "%s.open(False)"<CR>', explorer_page)
    exec printf('nnoremap <buffer> <silent> <2-LeftMouse> :exec g:Lf_py "%s.open(False)"<CR>', explorer_page)
    exec printf('nnoremap <buffer> <silent> <CR>          :exec g:Lf_py "%s.open(False)"<CR>', explorer_page)
    exec printf('nnoremap <buffer> <silent> O             :exec g:Lf_py "%s.open(True)"<CR>', explorer_page)
    exec printf('nnoremap <buffer> <silent> t             :exec g:Lf_py "%s.open(True, mode=''t'')"<CR>', explorer_page)
    exec printf('nnoremap <buffer> <silent> p             :exec g:Lf_py "%s.open(True, preview=True)"<CR>', explorer_page)
    exec printf('nnoremap <buffer> <silent> x             :call leaderf#Git#CollapseParent("%s")<CR>', explorer_page)
    exec printf('nnoremap <buffer> <silent> f             :exec g:Lf_py "%s.fuzzySearch()"<CR>', explorer_page)
    exec printf('nnoremap <buffer> <silent> F             :exec g:Lf_py "%s.fuzzySearch(True)"<CR>', explorer_page)
    nnoremap <buffer> <silent> q             :q<CR>
endfunction

function! leaderf#Git#TimerCallback(manager_id, id)
    exec g:Lf_py "import ctypes"
    exec g:Lf_py printf("ctypes.cast(%d, ctypes.py_object).value._callback(bang=True)", a:manager_id)
endfunction

function! leaderf#Git#WriteBuffer(view_id, id)
    exec g:Lf_py "import ctypes"
    exec g:Lf_py printf("ctypes.cast(%d, ctypes.py_object).value.writeBuffer()", a:view_id)
endfunction

function! leaderf#Git#Cleanup(owner_id, id)
    exec g:Lf_py "import ctypes"
    exec g:Lf_py printf("ctypes.cast(%d, ctypes.py_object).value.cleanup()", a:owner_id)
endfunction

function! leaderf#Git#Suicide(view_id)
    exec g:Lf_py "import ctypes"
    exec g:Lf_py printf("ctypes.cast(%d, ctypes.py_object).value.suicide()", a:view_id)
endfunction

function! leaderf#Git#Bufhidden(view_id)
    exec g:Lf_py "import ctypes"
    exec g:Lf_py printf("ctypes.cast(%d, ctypes.py_object).value.bufHidden()", a:view_id)
endfunction

function! leaderf#Git#CleanupExplorerPage(view_id)
    exec g:Lf_py "import ctypes"
    exec g:Lf_py printf("ctypes.cast(%d, ctypes.py_object).value.cleanupExplorerPage()", a:view_id)
endfunction

function! leaderf#Git#Commands()
    if !exists("g:Lf_GitCommands")
        let g:Lf_GitCommands = [
                    \ {"Leaderf git diff":                         "fuzzy search and view the diffs"},
                    \ {"Leaderf git diff --side-by-side":          "fuzzy search and view the side-by-side diffs"},
                    \ {"Leaderf git diff --side-by-side --current-file":"view the side-by-side diffs of the current file"},
                    \ {"Leaderf git diff --directly":              "view the diffs directly"},
                    \ {"Leaderf git diff --directly --position right":"view the diffs in the right split window"},
                    \ {"Leaderf git diff --cached":                "fuzzy search and view `git diff --cached`"},
                    \ {"Leaderf git diff --cached --side-by-side": "fuzzy search and view the side-by-side diffs of `git diff --cached`"},
                    \ {"Leaderf git diff --cached --directly":     "view `git diff --cached` directly"},
                    \ {"Leaderf git diff --cached --directly --position right": "view `git diff --cached` directly in the right split window"},
                    \ {"Leaderf git diff HEAD":                    "fuzzy search and view `git diff HEAD`"},
                    \ {"Leaderf git diff HEAD --side-by-side":     "fuzzy search and view the side-by-side diffs of `git diff HEAD`"},
                    \ {"Leaderf git diff HEAD --directly":         "view `git diff HEAD` directly"},
                    \ {"Leaderf git diff HEAD --directly --position right":     "view `git diff HEAD` directly in the right split window"},
                    \ {"Leaderf git log":                          "fuzzy search and view the log"},
                    \ {"Leaderf git log --directly":               "view the logs directly"},
                    \ {"Leaderf git log --explorer":               "fuzzy search and view the logs of in an explorer tabpage"},
                    \ {"Leaderf git log --explorer --navigation-position bottom": "specify the position of navigation panel in explorer tabpage"},
                    \ {"Leaderf git log --current-file":           "fuzzy search and view the logs of current file"},
                    \ ]
    endif

    return g:Lf_GitCommands
endfunction

function! leaderf#Git#NormalModeFilter(winid, key) abort
    let key = leaderf#RemapKey(g:Lf_PyEval("id(gitExplManager)"), get(g:Lf_KeyMap, a:key, a:key))

    if key ==# "e"
        exec g:Lf_py "gitExplManager.editCommand()"
    else
        return leaderf#NormalModeFilter(g:Lf_PyEval("id(gitExplManager)"), a:winid, a:key)
    endif

    return 1
endfunction

function! leaderf#Git#DefineSyntax() abort
    syntax region Lf_hl_gitStat start=/^---$/ end=/^ \d\+ files\? changed,/
    syn match Lf_hl_gitStatPath /^ \S*\%(\s*|\s*\d\+\s*+*-*$\)\@=/ display containedin=Lf_hl_gitStat contained
    syn match Lf_hl_gitStatPath /^ \S*\%(\s*|\s*Bin \d\+ -> \d\+ bytes\?$\)\@=/ display containedin=Lf_hl_gitStat contained
    syn match Lf_hl_gitStatPath /^ \S*\%( => \S*\s*|\s*\d\+\s*+*-*$\)\@=/ display containedin=Lf_hl_gitStat contained
    syn match Lf_hl_gitStatPath /\%(^ \S* => \)\@<=\S*\%(\s*|\s*\d\+\s*+*-*$\)\@=/ display containedin=Lf_hl_gitStat contained
    syn match Lf_hl_gitStatNumber /\%(^ \S*\%( => \S*\)\?\s*|\s*\)\@<=\d\+\%(\s*+*-*$\)\@=/ display containedin=Lf_hl_gitStat contained
    syn match Lf_hl_gitStatNumber /\%(^ \S*\%( => \S*\)\?\s*|\s*Bin \)\@<=\d\+ -> \d\+\%( bytes\?$\)\@=/ display containedin=Lf_hl_gitStat contained
    syn match Lf_hl_gitStatPlus /\%(^ \S*\%( => \S*\)\?\s*|\s*\d\+\s*\)\@<=+*\%(-*$\)\@=/ display containedin=Lf_hl_gitStat contained
    syn match Lf_hl_gitStatMinus /\%(^ \S*\%( => \S*\)\?\s*|\s*\d\+\s*+*\)\@<=-*$/ display containedin=Lf_hl_gitStat contained
    syn match gitIdentityHeader /^Committer:/ contained containedin=gitHead nextgroup=gitIdentity skipwhite contains=@NoSpell
endfunction

function! leaderf#Git#DiffOff(win_ids) abort
    for id in a:win_ids
        call win_execute(id, "diffoff")
    endfor
endfunction
