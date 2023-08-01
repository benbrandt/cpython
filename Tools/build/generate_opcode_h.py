# This script generates the opcode.h header file.

import sys
import tokenize

SCRIPT_NAME = "Tools/build/generate_opcode_h.py"
PYTHON_OPCODE = "Lib/opcode.py"

header = f"""
// Auto-generated by {SCRIPT_NAME} from {PYTHON_OPCODE}

#ifndef Py_OPCODE_H
#define Py_OPCODE_H
#ifdef __cplusplus
extern "C" {{
#endif


/* Instruction opcodes for compiled code */
""".lstrip()

footer = """

#ifdef __cplusplus
}
#endif
#endif /* !Py_OPCODE_H */
"""

internal_header = f"""
// Auto-generated by {SCRIPT_NAME} from {PYTHON_OPCODE}

#ifndef Py_INTERNAL_OPCODE_H
#define Py_INTERNAL_OPCODE_H
#ifdef __cplusplus
extern "C" {{
#endif

#ifndef Py_BUILD_CORE
#  error "this header requires Py_BUILD_CORE define"
#endif

#include "opcode.h"
""".lstrip()

internal_footer = """
#ifdef __cplusplus
}
#endif
#endif  // !Py_INTERNAL_OPCODE_H
"""

DEFINE = "#define {:<38} {:>3}\n"

UINT32_MASK = (1<<32)-1

def get_python_module_dict(filename):
    mod = {}
    with tokenize.open(filename) as fp:
        code = fp.read()
    exec(code, mod)
    return mod

def main(opcode_py,
         _opcode_metadata_py='Lib/_opcode_metadata.py',
         outfile='Include/opcode.h',
         opcode_targets_h='Python/opcode_targets.h',
         internaloutfile='Include/internal/pycore_opcode.h'):

    _opcode_metadata = get_python_module_dict(_opcode_metadata_py)

    opcode = get_python_module_dict(opcode_py)
    opmap = opcode['opmap']
    opname = opcode['opname']
    is_pseudo = opcode['is_pseudo']

    MIN_PSEUDO_OPCODE = opcode["MIN_PSEUDO_OPCODE"]
    MAX_PSEUDO_OPCODE = opcode["MAX_PSEUDO_OPCODE"]
    MIN_INSTRUMENTED_OPCODE = opcode["MIN_INSTRUMENTED_OPCODE"]

    NUM_OPCODES = len(opname)
    used = [ False ] * len(opname)
    next_op = 1

    for name, op in opmap.items():
        used[op] = True

    specialized_opmap = {}
    opname_including_specialized = opname.copy()
    for name in _opcode_metadata['_specialized_instructions']:
        while used[next_op]:
            next_op += 1
        specialized_opmap[name] = next_op
        opname_including_specialized[next_op] = name
        used[next_op] = True

    with open(outfile, 'w') as fobj, open(internaloutfile, 'w') as iobj:
        fobj.write(header)
        iobj.write(internal_header)

        for name in opname:
            if name in opmap:
                op = opmap[name]
                if op == MIN_PSEUDO_OPCODE:
                    fobj.write(DEFINE.format("MIN_PSEUDO_OPCODE", MIN_PSEUDO_OPCODE))
                if op == MIN_INSTRUMENTED_OPCODE:
                    fobj.write(DEFINE.format("MIN_INSTRUMENTED_OPCODE", MIN_INSTRUMENTED_OPCODE))

                fobj.write(DEFINE.format(name, op))

                if op == MAX_PSEUDO_OPCODE:
                    fobj.write(DEFINE.format("MAX_PSEUDO_OPCODE", MAX_PSEUDO_OPCODE))


        for name, op in specialized_opmap.items():
            fobj.write(DEFINE.format(name, op))

        iobj.write("\nextern const uint8_t _PyOpcode_Caches[256];\n")
        iobj.write("\nextern const uint8_t _PyOpcode_Deopt[256];\n")
        iobj.write("\n#ifdef NEED_OPCODE_TABLES\n")

        iobj.write("\nconst uint8_t _PyOpcode_Caches[256] = {\n")
        for name, entries in opcode["_inline_cache_entries"].items():
            iobj.write(f"    [{name}] = {entries},\n")
        iobj.write("};\n")

        deoptcodes = {}
        for basic, op in opmap.items():
            if not is_pseudo(op):
                deoptcodes[basic] = basic
        for basic, family in _opcode_metadata["_specializations"].items():
            for specialized in family:
                deoptcodes[specialized] = basic
        iobj.write("\nconst uint8_t _PyOpcode_Deopt[256] = {\n")
        for opt, deopt in sorted(deoptcodes.items()):
            iobj.write(f"    [{opt}] = {deopt},\n")
        iobj.write("};\n")
        iobj.write("#endif   // NEED_OPCODE_TABLES\n")

        fobj.write("\n")
        for i, (op, _) in enumerate(opcode["_nb_ops"]):
            fobj.write(DEFINE.format(op, i))

        iobj.write("\n")
        iobj.write(f"\nextern const char *const _PyOpcode_OpName[{NUM_OPCODES}];\n")
        iobj.write("\n#ifdef NEED_OPCODE_TABLES\n")
        iobj.write(f"const char *const _PyOpcode_OpName[{NUM_OPCODES}] = {{\n")
        for op, name in enumerate(opname_including_specialized):
            if name[0] != "<":
                op = name
            iobj.write(f'''    [{op}] = "{name}",\n''')
        iobj.write("};\n")
        iobj.write("#endif   // NEED_OPCODE_TABLES\n")

        iobj.write("\n")
        iobj.write("#define EXTRA_CASES \\\n")
        for i, flag in enumerate(used):
            if not flag:
                iobj.write(f"    case {i}: \\\n")
        iobj.write("        ;\n")

        fobj.write(footer)
        iobj.write(internal_footer)

    with open(opcode_targets_h, "w") as f:
        targets = ["_unknown_opcode"] * 256
        for op, name in enumerate(opname_including_specialized):
            if op < 256 and not name.startswith("<"):
                targets[op] = f"TARGET_{name}"

        f.write("static void *opcode_targets[256] = {\n")
        f.write(",\n".join([f"    &&{s}" for s in targets]))
        f.write("\n};\n")

    print(f"{outfile} regenerated from {opcode_py}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
