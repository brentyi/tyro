from __future__ import print_function

import logging
import re
import sys
from argparse import (
    SUPPRESS,
    Action,
    ArgumentParser,
    _AppendAction,
    _AppendConstAction,
    _CountAction,
    _HelpAction,
    _StoreConstAction,
    _VersionAction,
)
from collections import defaultdict
from functools import total_ordering
from itertools import starmap
from string import Template
from typing import Any, Dict, List
from typing import Optional as Opt
from typing import Union

# version detector. Precedence: installed dist, git, 'UNKNOWN'
try:
    from ._dist_ver import __version__
except ImportError:
    try:
        from setuptools_scm import get_version

        __version__ = get_version(root="..", relative_to=__file__)
    except (ImportError, LookupError):
        __version__ = "UNKNOWN"
__all__ = [
    "complete",
    "add_argument_to",
    "SUPPORTED_SHELLS",
    "FILE",
    "DIRECTORY",
    "DIR",
]
log = logging.getLogger(__name__)

SUPPORTED_SHELLS: List[str] = []
_SUPPORTED_COMPLETERS = {}
CHOICE_FUNCTIONS: Dict[str, Dict[str, str]] = {
    "file": {"bash": "_shtab_compgen_files", "zsh": "_files", "tcsh": "f"},
    "directory": {"bash": "_shtab_compgen_dirs", "zsh": "_files -/", "tcsh": "d"},
}
FILE = CHOICE_FUNCTIONS["file"]
DIRECTORY = DIR = CHOICE_FUNCTIONS["directory"]
FLAG_OPTION = (
    _StoreConstAction,
    _HelpAction,
    _VersionAction,
    _AppendConstAction,
    _CountAction,
)
OPTION_END = _HelpAction, _VersionAction
OPTION_MULTI = _AppendAction, _AppendConstAction, _CountAction
RE_ZSH_SPECIAL_CHARS = re.compile(r"([^\w\s.,()-])")  # excessive but safe


def mark_completer(shell):
    def wrapper(func):
        if shell not in SUPPORTED_SHELLS:
            SUPPORTED_SHELLS.append(shell)
        _SUPPORTED_COMPLETERS[shell] = func
        return func

    return wrapper


def get_completer(shell):
    try:
        return _SUPPORTED_COMPLETERS[shell]
    except KeyError:
        raise NotImplementedError(
            "shell (%s) must be in {%s}" % (shell, ",".join(SUPPORTED_SHELLS))
        )


@total_ordering
class Choice(object):
    """
    Placeholder to mark a special completion `<type>`.

    >>> ArgumentParser.add_argument(..., choices=[Choice("<type>")])
    """

    def __init__(self, choice_type: str, required: bool = False) -> None:
        """
        See below for parameters.

        choice_type  : internal `type` name
        required  : controls result of comparison to empty strings
        """
        self.required = required
        self.type = choice_type

    def __repr__(self) -> str:
        return self.type + ("" if self.required else "?")

    def __cmp__(self, other: object) -> int:
        if self.required:
            return 0 if other else -1
        return 0

    def __eq__(self, other: object) -> bool:
        return self.__cmp__(other) == 0

    def __lt__(self, other: object) -> bool:
        return self.__cmp__(other) < 0


class Optional(object):
    """Example: `ArgumentParser.add_argument(..., choices=Optional.FILE)`."""

    FILE = [Choice("file")]
    DIR = DIRECTORY = [Choice("directory")]


class Required(object):
    """Example: `ArgumentParser.add_argument(..., choices=Required.FILE)`."""

    FILE = [Choice("file", True)]
    DIR = DIRECTORY = [Choice("directory", True)]


def complete2pattern(opt_complete, shell, choice_type2fn) -> bool:
    return (
        opt_complete.get(shell, "")
        if isinstance(opt_complete, dict)
        else choice_type2fn[opt_complete]
    )


def wordify(string: str) -> str:
    """Replace non-word chars [-. ] with underscores [_]"""
    return re.compile(r"[-.\s:]").sub("_", string)


def get_public_subcommands(sub):
    """Get all the publicly-visible subcommands for a given subparser."""
    public_parsers = {id(sub.choices[i.dest]) for i in sub._get_subactions()}
    return {k for k, v in sub.choices.items() if id(v) in public_parsers}


def get_bash_commands(root_parser, root_prefix, choice_functions=None):
    """
    Recursive subcommand parser traversal, returning lists of information on
    commands (formatted for output to the completions script).
    printing bash helper syntax.

    Returns:
      subparsers  : list of subparsers for each parser
      option_strings  : list of options strings for each parser
      compgens  : list of shtab `.complete` functions corresponding to actions
      choices  : list of choices corresponding to actions
      nargs  : list of number of args allowed for each action (if not 0 or 1)
    """
    choice_type2fn = {k: v["bash"] for k, v in CHOICE_FUNCTIONS.items()}
    if choice_functions:
        choice_type2fn.update(choice_functions)

    def get_option_strings(parser):
        """Flattened list of all `parser`'s option strings."""
        return sum(
            (
                opt.option_strings
                for opt in parser._get_optional_actions()
                if opt.help != SUPPRESS
            ),
            [],
        )

    def recurse(parser, prefix):
        """recurse through subparsers, appending to the return lists"""
        subparsers = []
        option_strings = []
        compgens = []
        choices = []
        nargs = []

        # temp lists for recursion results
        sub_subparsers = []
        sub_option_strings = []
        sub_compgens = []
        sub_choices = []
        sub_nargs = []

        # positional arguments
        discovered_subparsers = []
        for i, positional in enumerate(parser._get_positional_actions()):
            if positional.help == SUPPRESS:
                continue

            if hasattr(positional, "complete"):
                # shtab `.complete = ...` functions
                compgens.append(
                    "{}_pos_{}_COMPGEN={}".format(
                        prefix,
                        i,
                        complete2pattern(positional.complete, "bash", choice_type2fn),
                    )
                )

            if positional.choices:
                # choices (including subparsers & shtab `.complete` functions)
                log.debug("choices:{}:{}".format(prefix, sorted(positional.choices)))

                this_positional_choices = []
                for choice in positional.choices:
                    if isinstance(choice, Choice):
                        # append special completion type to `compgens`
                        # NOTE: overrides `.complete` attribute
                        log.debug(
                            "Choice.{}:{}:{}".format(
                                choice.type, prefix, positional.dest
                            )
                        )
                        compgens.append(
                            "{}_pos_{}_COMPGEN={}".format(
                                prefix, i, choice_type2fn[choice.type]
                            )
                        )
                    elif isinstance(positional.choices, dict):
                        # subparser, so append to list of subparsers & recurse
                        log.debug("subcommand:%s", choice)
                        public_cmds = get_public_subcommands(positional)
                        if choice in public_cmds:
                            discovered_subparsers.append(str(choice))
                            this_positional_choices.append(str(choice))
                            (
                                new_subparsers,
                                new_option_strings,
                                new_compgens,
                                new_choices,
                                new_nargs,
                            ) = recurse(
                                positional.choices[choice],
                                prefix + "_" + wordify(choice),
                            )
                            sub_subparsers.extend(new_subparsers)
                            sub_option_strings.extend(new_option_strings)
                            sub_compgens.extend(new_compgens)
                            sub_choices.extend(new_choices)
                            sub_nargs.extend(new_nargs)
                        else:
                            log.debug("skip:subcommand:%s", choice)
                    else:
                        # simple choice
                        this_positional_choices.append(str(choice))

                if this_positional_choices:
                    choices.append(
                        "{}_pos_{}_choices=('{}')".format(
                            prefix, i, "' '".join(this_positional_choices)
                        )
                    )

            # skip default `nargs` values
            if positional.nargs not in (None, "1", "?"):
                nargs.append("{}_pos_{}_nargs={}".format(prefix, i, positional.nargs))

        if discovered_subparsers:
            subparsers.append(
                "{}_subparsers=('{}')".format(prefix, "' '".join(discovered_subparsers))
            )
            log.debug("subcommands:{}:{}".format(prefix, discovered_subparsers))

        # optional arguments
        option_strings.append(
            "{}_option_strings=('{}')".format(
                prefix, "' '".join(get_option_strings(parser))
            )
        )
        for optional in parser._get_optional_actions():
            if optional == SUPPRESS:
                continue

            for option_string in optional.option_strings:
                if hasattr(optional, "complete"):
                    # shtab `.complete = ...` functions
                    compgens.append(
                        "{}_{}_COMPGEN={}".format(
                            prefix,
                            wordify(option_string),
                            complete2pattern(optional.complete, "bash", choice_type2fn),
                        )
                    )

                if optional.choices:
                    # choices (including shtab `.complete` functions)
                    this_optional_choices = []
                    for choice in optional.choices:
                        # append special completion type to `compgens`
                        # NOTE: overrides `.complete` attribute
                        if isinstance(choice, Choice):
                            log.debug(
                                "Choice.{}:{}:{}".format(
                                    choice.type, prefix, optional.dest
                                )
                            )
                            compgens.append(
                                "{}_{}_COMPGEN={}".format(
                                    prefix,
                                    wordify(option_string),
                                    choice_type2fn[choice.type],
                                )
                            )
                        else:
                            # simple choice
                            this_optional_choices.append(str(choice))

                    if this_optional_choices:
                        choices.append(
                            "{}_{}_choices=('{}')".format(
                                prefix,
                                wordify(option_string),
                                "' '".join(this_optional_choices),
                            )
                        )

                # Check for nargs.
                if optional.nargs is not None and optional.nargs != 1:
                    nargs.append(
                        "{}_{}_nargs={}".format(
                            prefix, wordify(option_string), optional.nargs
                        )
                    )

        # append recursion results
        subparsers.extend(sub_subparsers)
        option_strings.extend(sub_option_strings)
        compgens.extend(sub_compgens)
        choices.extend(sub_choices)
        nargs.extend(sub_nargs)

        return subparsers, option_strings, compgens, choices, nargs

    return recurse(root_parser, root_prefix)


@mark_completer("bash")
def complete_bash(parser, root_prefix=None, preamble="", choice_functions=None):
    """
    Returns bash syntax autocompletion script.

    See `complete` for arguments.
    """
    root_prefix = wordify("_shtab_" + (root_prefix or parser.prog))
    subparsers, option_strings, compgens, choices, nargs = get_bash_commands(
        parser, root_prefix, choice_functions=choice_functions
    )

    # References:
    # - https://www.gnu.org/software/bash/manual/html_node/
    #   Programmable-Completion.html
    # - https://opensource.com/article/18/3/creating-bash-completion-script
    # - https://stackoverflow.com/questions/12933362
    return Template(
        """\
# AUTOMATCALLY GENERATED by `shtab`

${subparsers}

${option_strings}

${compgens}

${choices}

${nargs}

${preamble}
# $1=COMP_WORDS[1]
_shtab_compgen_files() {
  compgen -f -- $1  # files
}

# $1=COMP_WORDS[1]
_shtab_compgen_dirs() {
  compgen -d -- $1  # recurse into subdirs
}

# $1=COMP_WORDS[1]
_shtab_replace_nonword() {
  echo "${1//[^[:word:]]/_}"
}

# set default values (called for the initial parser & any subparsers)
_set_parser_defaults() {
  local subparsers_var="${prefix}_subparsers[@]"
  sub_parsers=${!subparsers_var}

  local current_option_strings_var="${prefix}_option_strings[@]"
  current_option_strings=${!current_option_strings_var}

  completed_positional_actions=0

  _set_new_action "pos_${completed_positional_actions}" true
}

# $1=action identifier
# $2=positional action (bool)
# set all identifiers for an action's parameters
_set_new_action() {
  current_action="${prefix}_$(_shtab_replace_nonword $1)"

  local current_action_compgen_var=${current_action}_COMPGEN
  current_action_compgen="${!current_action_compgen_var}"

  local current_action_choices_var="${current_action}_choices[@]"
  current_action_choices="${!current_action_choices_var}"

  local current_action_nargs_var="${current_action}_nargs"
  if [ -n "${!current_action_nargs_var}" ]; then
    current_action_nargs="${!current_action_nargs_var}"
  else
    current_action_nargs=1
  fi

  current_action_args_start_index=$(( $word_index + 1 ))

  current_action_is_positional=$2
}

# Notes:
# `COMPREPLY`: what will be rendered after completion is triggered
# `completing_word`: currently typed word to generate completions for
# `${!var}`: evaluates the content of `var` and expand its content as a variable
#     hello="world"
#     x="hello"
#     ${!x} -> ${hello} -> "world"
${root_prefix}() {
  local completing_word="${COMP_WORDS[COMP_CWORD]}"
  COMPREPLY=()

  prefix=${root_prefix}
  word_index=0
  _set_parser_defaults
  word_index=1

  # determine what arguments are appropriate for the current state
  # of the arg parser
  while [ $word_index -ne $COMP_CWORD ]; do
    local this_word="${COMP_WORDS[$word_index]}"

    if [[ -n $sub_parsers && " ${sub_parsers[@]} " =~ " ${this_word} " ]]; then
      # valid subcommand: add it to the prefix & reset the current action
      prefix="${prefix}_$(_shtab_replace_nonword $this_word)"
      _set_parser_defaults
    fi

    if [[ " ${current_option_strings[@]} " =~ " ${this_word} " ]]; then
      # a new action should be acquired (due to recognised option string or
      # no more input expected from current action);
      # the next positional action can fill in here
      _set_new_action $this_word false
    fi

    if [[ "$current_action_nargs" != "*" ]] && \\
       [[ "$current_action_nargs" != "+" ]] && \\
       [[ "$current_action_nargs" != *"..." ]] && \\
       (( $word_index + 1 - $current_action_args_start_index >= \\
          $current_action_nargs )); then
      $current_action_is_positional && let "completed_positional_actions += 1"
      _set_new_action "pos_${completed_positional_actions}" true
    fi

    let "word_index+=1"
  done

  # Generate the completions

  if [[ "${completing_word}" == -* ]]; then
    # optional argument started: use option strings
    COMPREPLY=( $(compgen -W "${current_option_strings[*]}" -- "${completing_word}") )
  else
    # use choices & compgen
    COMPREPLY=( $(compgen -W "${current_action_choices[*]}" -- "${completing_word}") \\
                $([ -n "${current_action_compgen}" ] \\
                  && "${current_action_compgen}" "${completing_word}") )
  fi

  return 0
}

complete -o filenames -F ${root_prefix} ${prog}"""
    ).safe_substitute(
        subparsers="\n".join(subparsers),
        option_strings="\n".join(option_strings),
        compgens="\n".join(compgens),
        choices="\n".join(choices),
        nargs="\n".join(nargs),
        preamble=(
            "\n# Custom Preamble\n" + preamble + "\n# End Custom Preamble\n"
            if preamble
            else ""
        ),
        root_prefix=root_prefix,
        prog=parser.prog,
    )


def escape_zsh(string):
    return RE_ZSH_SPECIAL_CHARS.sub(r"\\\1", str(string))


@mark_completer("zsh")
def complete_zsh(parser, root_prefix=None, preamble="", choice_functions=None):
    """
    Returns zsh syntax autocompletion script.

    See `complete` for arguments.
    """
    prog = parser.prog
    root_prefix = wordify("_shtab_" + (root_prefix or prog))

    choice_type2fn = {k: v["zsh"] for k, v in CHOICE_FUNCTIONS.items()}
    if choice_functions:
        choice_type2fn.update(choice_functions)

    def format_optional(opt):
        return (
            (
                '{nargs}{options}"[{help}]"'
                if isinstance(opt, FLAG_OPTION)
                else '{nargs}{options}"[{help}]:{dest}:{pattern}"'
            )
            .format(
                nargs=(
                    '"(- :)"'
                    if isinstance(opt, OPTION_END)
                    else '"*"'
                    if isinstance(opt, OPTION_MULTI)
                    else ""
                ),
                options=(
                    "{{{}}}".format(",".join(opt.option_strings))
                    if len(opt.option_strings) > 1
                    else '"{}"'.format("".join(opt.option_strings))
                ),
                help=escape_zsh(opt.help or ""),
                dest=opt.dest,
                pattern=complete2pattern(opt.complete, "zsh", choice_type2fn)
                if hasattr(opt, "complete")
                else (
                    choice_type2fn[opt.choices[0].type]
                    if isinstance(opt.choices[0], Choice)
                    else "({})".format(" ".join(map(str, opt.choices)))
                )
                if opt.choices
                else "",
            )
            .replace('""', "")
        )

    def format_positional(opt):
        return '"{nargs}:{help}:{pattern}"'.format(
            nargs={"+": "(*)", "*": "(*):"}.get(opt.nargs, ""),
            help=escape_zsh((opt.help or opt.dest).strip().split("\n")[0]),
            pattern=complete2pattern(opt.complete, "zsh", choice_type2fn)
            if hasattr(opt, "complete")
            else (
                choice_type2fn[opt.choices[0].type]
                if isinstance(opt.choices[0], Choice)
                else "({})".format(" ".join(map(str, opt.choices)))
            )
            if opt.choices
            else "",
        )

    # {cmd: {"help": help, "arguments": [arguments]}}
    all_commands = {
        root_prefix: {
            "cmd": prog,
            "arguments": [
                format_optional(opt)
                for opt in parser._get_optional_actions()
                if opt.help != SUPPRESS
            ],
            "help": (parser.description or "").strip().split("\n")[0],
            "commands": [],
            "paths": [],
        }
    }

    def recurse(parser, prefix, paths=None):
        paths = paths or []
        subcmds = []
        for sub in parser._get_positional_actions():
            if sub.help == SUPPRESS or not sub.choices:
                continue
            if not sub.choices or not isinstance(sub.choices, dict):
                # positional argument
                all_commands[prefix]["arguments"].append(format_positional(sub))
            else:  # subparser
                log.debug("choices:{}:{}".format(prefix, sorted(sub.choices)))
                public_cmds = get_public_subcommands(sub)
                for cmd, subparser in sub.choices.items():
                    if cmd not in public_cmds:
                        log.debug("skip:subcommand:%s", cmd)
                        continue
                    log.debug("subcommand:%s", cmd)

                    # optionals
                    arguments = [
                        format_optional(opt)
                        for opt in subparser._get_optional_actions()
                        if opt.help != SUPPRESS
                    ]

                    # positionals
                    arguments.extend(
                        format_positional(opt)
                        for opt in subparser._get_positional_actions()
                        if not isinstance(opt.choices, dict)
                        if opt.help != SUPPRESS
                    )

                    new_pref = prefix + "_" + wordify(cmd)
                    options = all_commands[new_pref] = {
                        "cmd": cmd,
                        "help": (subparser.description or "").strip().split("\n")[0],
                        "arguments": arguments,
                        "paths": [*paths, cmd],
                    }
                    new_subcmds = recurse(subparser, new_pref, [*paths, cmd])
                    options["commands"] = {
                        all_commands[pref]["cmd"]: all_commands[pref]
                        for pref in new_subcmds
                        if pref in all_commands
                    }
                    subcmds.extend([*new_subcmds, new_pref])
                    log.debug("subcommands:%s:%s", cmd, options)
        return subcmds

    recurse(parser, root_prefix)
    all_commands[root_prefix]["commands"] = {
        options["cmd"]: options
        for prefix, options in sorted(all_commands.items())
        if len(options.get("paths", [])) < 2 and prefix != root_prefix
    }
    subcommands = {
        prefix: options
        for prefix, options in all_commands.items()
        if options.get("commands")
    }
    subcommands.setdefault(root_prefix, all_commands[root_prefix])
    log.debug("subcommands:%s:%s", root_prefix, sorted(all_commands))

    def command_case(prefix, options):
        name = options["cmd"]
        commands = options["commands"]
        case_fmt_on_no_sub = (
            """{name}) _arguments -C ${prefix}_{name_wordify}_options ;;"""
        )
        case_fmt_on_sub = """{name}) {prefix}_{name_wordify} ;;"""

        cases = []
        for _, options in sorted(commands.items()):
            fmt = case_fmt_on_sub if options.get("commands") else case_fmt_on_no_sub
            cases.append(
                fmt.format(
                    name=options["cmd"],
                    name_wordify=wordify(options["cmd"]),
                    prefix=prefix,
                )
            )
        cases = "\n\t".expandtabs(8).join(cases)

        return """\
{prefix}() {{
  local context state line curcontext="$curcontext"

  _arguments -C ${prefix}_options \\
    ': :{prefix}_commands' \\
    '*::: :->{name}'

  case $state in
    {name})
      words=($line[1] "${{words[@]}}")
      (( CURRENT += 1 ))
      curcontext="${{curcontext%:*:*}}:{prefix}-$line[1]:"
      case $line[1] in
        {cases}
      esac
  esac
}}
""".format(
            prefix=prefix, name=name, cases=cases
        )

    def command_option(prefix, options):
        return """\
{prefix}_options=(
  {arguments}
)
""".format(
            prefix=prefix, arguments="\n  ".join(options["arguments"])
        )

    def command_list(prefix, options):
        name = " ".join([prog, *options["paths"]])
        commands = "\n    ".join(
            '"{}:{}"'.format(escape_zsh(cmd), escape_zsh(opt["help"]))
            for cmd, opt in sorted(options["commands"].items())
        )
        return """
{prefix}_commands() {{
  local _commands=(
    {commands}
  )
  _describe '{name} commands' _commands
}}""".format(
            prefix=prefix, name=name, commands=commands
        )

    preamble = (
        """\
# Custom Preamble
{}

# End Custom Preamble
""".format(
            preamble.rstrip()
        )
        if preamble
        else ""
    )
    # References:
    #   - https://github.com/zsh-users/zsh-completions
    #   - http://zsh.sourceforge.net/Doc/Release/Completion-System.html
    #   - https://mads-hartmann.com/2017/08/06/
    #     writing-zsh-completion-scripts.html
    #   - http://www.linux-mag.com/id/1106/
    return Template(
        """\
#compdef ${prog}

# AUTOMATCALLY GENERATED by `shtab`

${command_commands}

${command_options}

${command_cases}
${preamble}

typeset -A opt_args
${root_prefix} "$@\""""
    ).safe_substitute(
        prog=prog,
        root_prefix=root_prefix,
        command_cases="\n".join(starmap(command_case, sorted(subcommands.items()))),
        command_commands="\n".join(starmap(command_list, sorted(subcommands.items()))),
        command_options="\n".join(
            starmap(command_option, sorted(all_commands.items()))
        ),
        preamble=preamble,
    )


@mark_completer("tcsh")
def complete_tcsh(parser, root_prefix=None, preamble="", choice_functions=None):
    """
    Return tcsh syntax autocompletion script.

    See `complete` for arguments.
    """
    optionals_single = set()
    optionals_double = set()
    specials = []
    index_choices = defaultdict(dict)

    choice_type2fn = {k: v["tcsh"] for k, v in CHOICE_FUNCTIONS.items()}
    if choice_functions:
        choice_type2fn.update(choice_functions)

    def get_specials(arg, arg_type, arg_sel):
        if arg.choices:
            choice_strs = " ".join(map(str, arg.choices))
            yield "'{}/{}/({})/'".format(
                arg_type,
                arg_sel,
                choice_strs,
            )
        elif hasattr(arg, "complete"):
            complete_fn = complete2pattern(arg.complete, "tcsh", choice_type2fn)
            if complete_fn:
                yield "'{}/{}/{}/'".format(
                    arg_type,
                    arg_sel,
                    complete_fn,
                )

    def recurse_parser(cparser, positional_idx, requirements=None):
        log_prefix = "| " * positional_idx
        log.debug("%sParser @ %d", log_prefix, positional_idx)
        if requirements:
            log.debug("%s- Requires: %s", log_prefix, " ".join(requirements))
        else:
            requirements = []

        for optional in cparser._get_optional_actions():
            log.debug("%s| Optional: %s", log_prefix, optional.dest)
            if optional.help != SUPPRESS:
                # Mingle all optional arguments for all subparsers
                for optional_str in optional.option_strings:
                    log.debug("%s| | %s", log_prefix, optional_str)
                    if optional_str.startswith("--"):
                        optionals_double.add(optional_str[2:])
                    elif optional_str.startswith("-"):
                        optionals_single.add(optional_str[1:])
                    specials.extend(get_specials(optional, "n", optional_str))

        for positional in cparser._get_positional_actions():
            if positional.help != SUPPRESS:
                positional_idx += 1
                log.debug(
                    "%s| Positional #%d: %s",
                    log_prefix,
                    positional_idx,
                    positional.dest,
                )
                index_choices[positional_idx][tuple(requirements)] = positional
                if not requirements and isinstance(positional.choices, dict):
                    for subcmd, subparser in positional.choices.items():
                        log.debug("%s| | SubParser: %s", log_prefix, subcmd)
                        recurse_parser(
                            subparser, positional_idx, requirements + [subcmd]
                        )

    recurse_parser(parser, 0)

    for idx, ndict in index_choices.items():
        if len(ndict) == 1:
            # Single choice, no requirements
            arg = list(ndict.values())[0]
            specials.extend(get_specials(arg, "p", str(idx)))
        else:
            # Multiple requirements
            nlist = []
            for nn, arg in ndict.items():
                checks = [
                    '[ "$cmd[{}]" == "{}" ]'.format(iidx, n)
                    for iidx, n in enumerate(nn, start=2)
                ]
                if arg.choices:
                    nlist.append(
                        '( {}echo "{}" || false )'.format(
                            " && ".join(checks + [""]),  # Append the separator
                            "\\n".join(arg.choices),
                        )
                    )

            # Ugly hack
            specials.append(
                "'p@{}@`set cmd=($COMMAND_LINE); {}`@'".format(
                    str(idx), " || ".join(nlist)
                )
            )

    return Template(
        """\
# AUTOMATICALLY GENERATED by `shtab`

${preamble}

complete ${prog} \\
        'c/--/(${optionals_double_str})/' \\
        'c/-/(${optionals_single_str} -)/' \\
        ${optionals_special_str} \\
        'p/*/()/'"""
    ).safe_substitute(
        preamble=(
            "\n# Custom Preamble\n" + preamble + "\n# End Custom Preamble\n"
            if preamble
            else ""
        ),
        root_prefix=root_prefix,
        prog=parser.prog,
        optionals_double_str=" ".join(optionals_double),
        optionals_single_str=" ".join(optionals_single),
        optionals_special_str=" \\\n        ".join(specials),
    )


def complete(
    parser: ArgumentParser,
    shell: str = "bash",
    root_prefix: Opt[str] = None,
    preamble: Union[str, Dict] = "",
    choice_functions: Opt[Any] = None,
) -> str:
    """
    parser  : argparse.ArgumentParser
    shell  : str (bash/zsh)
    root_prefix  : str or `None`
      prefix for shell functions to avoid clashes (default: "_{parser.prog}")
    preamble  : dict or str
      mapping shell to text to prepend to generated script
      (e.g. `{"bash": "_myprog_custom_function(){ echo hello }"}`)
    choice_functions  : deprecated

    N.B. `parser.add_argument().complete = ...` can be used to define custom
    completions (e.g. filenames). See <../examples/pathcomplete.py>.
    """
    if isinstance(preamble, dict):
        preamble = preamble.get(shell, "")
    completer = get_completer(shell)
    return completer(
        parser,
        root_prefix=root_prefix,
        preamble=preamble,
        choice_functions=choice_functions,
    )


def completion_action(parent=None, preamble=""):
    class PrintCompletionAction(Action):
        def __call__(self, parser, namespace, values, option_string=None):
            print(complete(parent or parser, values, preamble=preamble))
            parser.exit(0)

    return PrintCompletionAction


def add_argument_to(
    parser,
    option_string="--print-completion",
    help="print shell completion script",
    parent=None,
    preamble="",
):
    """
    parser  : argparse.ArgumentParser
    option_string  : str or list[str]
      iff positional (no `-` prefix) then `parser` is assumed to actually be
      a subparser (subcommand mode)
    help  : str
    parent  : argparse.ArgumentParser
      required in subcommand mode
    """
    if isinstance(
        option_string, str if sys.version_info[0] > 2 else basestring  # NOQA
    ):
        option_string = [option_string]
    kwargs = {
        "choices": SUPPORTED_SHELLS,
        "default": None,
        "help": help,
        "action": completion_action(parent, preamble),
    }
    if option_string[0][0] != "-":  # subparser mode
        kwargs.update(default=SUPPORTED_SHELLS[0], nargs="?")
        assert parent is not None, "subcommand mode: parent required"
    parser.add_argument(*option_string, **kwargs)
    return parser
