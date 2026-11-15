'''
CIE Pseudocode Interpreter v1.0.0 alpha
Unsupported:
    Type validation
    Syntax validation (Assumes the user writes correct code)
    Proper error messages
    Self defined types
    Pointers
    File operations
    DATE data type
    Non 1 indexed ARRAYS
    OOP
'''


from re import L
import sys
from random import random
if len(sys.argv) != 2:
    print("Usage: python pseudocode_interpreter.py <path_to_file>")
    sys.exit(1)

path = sys.argv[1]

global pseudocode, subprocs, DEFAULT_VALS, next_point, global_vars

try:
    with open(path, 'r') as file:
       split_code = file.read().splitlines() 
except FileNotFoundError:
    print(f"Error: File not found")
    exit(1)

def blank_line(line):
    for n, i in enumerate(line):
        if i!=' ' and i!='\t':
            if line[n] == "/" and line[n+1] == "/": #if the entire line is just a comment
                return True
            return False
    return True

#parse the code
#combos: <-, <=, >=, <>, //
split_code = [i for i in split_code if not blank_line(i)] #remove blank lines
pseudocode = [[] for _ in split_code] #initialise
for n, line in enumerate(split_code):
    if blank_line(line):
        continue
    cur = ""
    in_string = False
    for i in line:
        if i == "\t":
            continue
        if i=='"':
            if not in_string: #opening
                if cur!="":
                    pseudocode[n].append(cur)
                cur = '"'
            else: #closing
                pseudocode[n].append(cur+'"')
                cur = ""
            in_string = not in_string
        elif in_string:
            cur+=i
        else:
            if i == " ":
                if cur!="":
                   pseudocode[n].append(cur)
                   cur=""
            elif i == "/" and pseudocode[n] and pseudocode[n][-1]=="/": #comments
                pseudocode[n].pop()
                cur = ""
                break
            elif i == "(": #should be parsed into ["foo(", "bar", ")"]
                pseudocode[n].append(cur+i)
                cur = ""
            elif i in "-=>" and cur=="" and ( #combos
                i=="-" and pseudocode[n][-1]=="<" or
                i=="=" and pseudocode[n][-1]=="<" or
                i=="=" and pseudocode[n][-1]==">" or
                i==">" and pseudocode[n][-1]=="<"
            ):
                pseudocode[n][-1]+=i
            elif i in ",+-*/^<>=&)[]:":
                if cur!="":
                    pseudocode[n].append(cur)
                    cur = ""
                pseudocode[n].append(i)
            else:
                cur+=i
    
    if cur!="":
        pseudocode[n].append(cur)

#change val1 : statement to be in different lines, occurs when : without DECLARE etc.
i=0
while i<len(pseudocode):
    if ":" in pseudocode[i] and pseudocode[i][0] not in ["DECLARE", "PROCEDURE", "FUNCTION"]:
        colon_idx = pseudocode[i].index(":")
        if colon_idx != len(pseudocode[i])-1: #if nothing after colon
            pseudocode.insert(i+1, pseudocode[i][colon_idx+1:])
            pseudocode[i] = pseudocode[i][:colon_idx+1]
    i+=1

subprocs = {} #func: [[byval/byref, arg1], [byval/byref, arg2]]
global_vars = {}
DEFAULT_VALS = {"INTEGER" : "0", "BOOLEAN" : "FALSE", "STRING" : '""', "CHAR" : "''", "REAL" : "0.0"}

def valid_var(s): #check if a string is a valid variable name
    if s[0].isnumeric():
        return False
    for i in s:
        if not i.isalpha() and not i.isnumeric() and i!='_':
            return False
    return True

#WHILE ENDWHILE
#FOR NEXT Var
#CASE ENDCASE
#IF ELSE ENDIF
#REPEAT UNTIL
#PROCEDURE ENDPROCEDURE
#FUNCTION ENDFUNCTION

CORRESPONDING = {
    "ENDWHILE" : "WHILE",
    "NEXT" : "FOR",
    "UNIL" : "REPEAT",
    "ENDPROCEDURE" : "PROCEDURE",
    "ENDFUNCTION" : "FUNCTION",
    "ELSE" : "IF",
    ":" : ":"
    #special handling required for ENDIF, and ENDCASE
}
#: refers to the ":" in case statements:
#e.g. val1 : statement

next_point = {}
loop_start = {}
flow_stack = { "WHILE" : [], "FOR" : [], ":" : [], "IF" : [], "ELSE" : [], "CASE" : [], "REPEAT" : [], "PROCEDURE" : [], "FUNCTION" : [] }

for n,i in enumerate(pseudocode):
    if i[0] in flow_stack:
        flow_stack[i[0]].append(n)
    elif i[0] == "ENDIF":
        if not flow_stack["ELSE"] or flow_stack["IF"] and flow_stack["IF"][-1] > flow_stack["ELSE"][-1]:
            #IF ENDIF instead of IF ELSE ENDIF
            #Happens if IF is more recent than ELSE
            next_point[flow_stack["IF"][-1]] = n 
            flow_stack["IF"].pop()
        else:
            next_point[flow_stack["ELSE"][-1]] = n
            flow_stack["ELSE"].pop()
    elif i[0] == "ENDCASE":
        #edge detection for CASE, ENDCASE with nothing inside it
        next_point[flow_stack["CASE"][-1]] = n
        flow_stack["CASE"].pop()
        if pseudocode[n-1][0] == "CASE":
            continue
        #otherwise, find the most recent ":"
        next_point[flow_stack[":"][-1]] = n
        flow_stack[":"].pop()

    #fill in the general case
    if i[0] in CORRESPONDING:
        if i[0] in ["ENDWHILE", "NEXT", "UNTIL"]:
            loop_start[n]=flow_stack[CORRESPONDING[i[0]]][-1]
        next_point[flow_stack[CORRESPONDING[i[0]]][-1]] = n
        flow_stack[CORRESPONDING[i[0]]].pop()
    elif i[-1] == ":":
        #edge case for the first ":" after a CASE statement. Don't fill in
        if pseudocode[n-1][0] == "CASE":
            flow_stack[":"].append(n)
            continue
        next_point[flow_stack[":"][-1]] = n
        flow_stack[":"][-1] = n #replace instead of popping

#Operators: + - * / ^ ( ) [ ] & NOT AND OR = <> < > <= >=
#Order: ^, (*, /, MOD), (+, -, &)
#Functions: DIV, MOD, LENGTH, IS_NUM, INT, NUM_TO_STRING, LEFT, RIGHT, SUBSTRING, UCASE, LCASE, ASC, CHR

def execute(proc, args, external_vars, available_references):
    if proc in subprocs:
        arg_names = []
        references = {}
        for n, i in enumerate(subprocs[proc][1]): #subprocs: idx, [[BYVAL/BYREF, arg1], [BYVAL/BYREF, arg2]
            if i[0] == "BYREF" and n in available_references:
                references[i[1]] = available_references[n]
                #available_references stores what the nth argument refers to (if applicable)
                #so store the argument name as a reference to what it refers to instead
            arg_names.append(i[1])
        local_vars = dict(zip(arg_names, args))
        val = interpret(subprocs[proc][0]+1, local_vars, external_vars, references)
        return val
    if proc == "":
        return args[0]
    if proc == "DIV":
        return str(int(float(args[0])//float(args[1])))
    if proc == "MOD":
        tmp = float(args[0])%float(args[1])
        if float(int(tmp)) == tmp:
            tmp = int(tmp)
        return str(tmp)
    if proc == "LENGTH":
        return str(len(args[0])-2)
    if proc == "IS_NUM":
        try:
            float(args[0][1:-1])
            return "TRUE"
        except:
            return "FALSE"
    if proc == "INT":
        if args[0][0] == '"' or args[0][0] == "'":
            return str(int(args[0][1:-1]))
        else:
            return str(int(float(args[0])))
    if proc in ["NUM_TO_STRING", "NUM_TO_STR"]:
        return '"' + args[0] + '"'
    if proc in ["STRING_TO_NUM", "STR_TO_NUM"]:
        return args[0][1:-1]
    if proc == "LEFT":
        return args[0][:int(args[1])+1] + '"'
    if proc == "RIGHT":
        return '"' + args[0][-int(args[1])-1:]
    if proc in ["MID", "SUBSTRING", "SUBSTR"]: #one indexed
        return '"' + args[0][int(args[1]) : int(args[1]) + int(args[2])] + '"'
    if proc == "UCASE":
        return args[0].upper()
    if proc == "LCASE":
        return args[0].lower()
    if proc == "ASC":
        return str(ord(args[0][1]))
    if proc == "CHR":
        return "'"+str(chr(int(args[0])))+"'"
    if proc == "RAND":
        return str(random()*int(args[0]))

def make_array(shape, val):
    if not shape:
        return val
    return [make_array(shape[1:], val) for _ in range(int(shape[0]))]

def deepcopy(arr):
    out = arr.copy()
    for n, i in enumerate(arr):
        if type(i) is list:
            out[n] = deepcopy(i)
    return out

def evaluate(expr, declared_vars):
    #Evaluate everything in brackets first (flatten, so only Opeartors are left)
    open_brackets = 0
    cur_idx = 0
    i = 0
    while i < len(expr):
        if expr[i][-1] == "(" or expr[i] == "[":
            if open_brackets==0:
                cur_idx = i+1
            open_brackets += 1
        elif expr[i] in ")]":
            open_brackets -= 1
            if open_brackets == 0:
                #prepare to call subprocess
                #look for comma sepeartion
                args = [[]]
                evaluated_args = []
                available_references = {}
                #format { n : ... }
                #indicates that the nth argument is able to be added by reference, and refers to ...
                inner_loop_open_brackets = 0
                for j in range(cur_idx, i):
                    if expr[j]=="," and inner_loop_open_brackets==0:
                        args.append([])
                    else:
                        if expr[j][-1] == "(" or expr[j] == '[':
                            inner_loop_open_brackets += 1
                        if expr[j] in ")]":
                            inner_loop_open_brackets -= 1
                        args[-1].append(expr[j])
                for n, j in enumerate(args):
                    if j == []:
                        break
                    #check if j is in the form of arr[idx1, idx2...] for BYREF function calls
                    #idx should already by evaluated for inputting arrays.
                    if expr[i] == ")":
                        if len(j) == 1 and j[0] in declared_vars:
                            #check for func(var)
                            #in which case, it is possible (but not guranteed) to input by reference
                            available_references[n] = j[0]
                        elif len(j)>=3 and j[0] in declared_vars and j[1] == "[" and j[-1] == "]":
                            #func(arr[...])
                            #which is also possible to input by reference
                            #parse the "[", ..., "]" with evaluate
                            index_array = evaluate(j[1:], declared_vars)
                            #access the index
                            arr = declared_vars[j[0]]
                            for idx in index_array:
                                arr = arr[int(idx)-1]
                            #arr is now the required value
                            evaluated_args.append(arr)
                            available_references[n] = [j[0], index_array]
                            #store the original arr_name and the index that is referenced instead of just var_name
                            continue #we must avoid evaluating again
                    evaluated_args.append(evaluate(j, declared_vars))

                #evaluated_args = [arg1, arg2, arg3]
           
                if expr[i] == ')':
                    proc = expr[cur_idx-1][:-1]
                    expr[cur_idx-1:i+1]=[execute(proc, evaluated_args, declared_vars, available_references)]
                    i = cur_idx - 1
                else:
                    #basic parsing for array literals/index access
                    #"[a, b, c]" into [eval(a), eval(b), eval(c)]
                    expr[cur_idx-1:i+1] = [evaluated_args]
                    i = cur_idx-1
        i+=1

    #replace variables
    for i in range(len(expr)):
        if type(expr[i]) is not list and expr[i] in declared_vars:
            expr[i]=declared_vars[expr[i]]
    
    # index access
    i=0
    while i < len(expr)-1:
        if type(expr[i+1]) is list and type(expr[i]) is list:
            tmp = expr[i]
            for idx in expr[i+1]: #size of expr[i+1] = dimensions of expr[i]
                tmp = tmp[int(idx)-1] #pseudocode is 1 indexed
            expr[i:i+2] = [tmp]
        i+=1

    # power
    i=0
    while i < len(expr)-1:
        if expr[i+1] == "^":
            tmp = float(expr[i])*float(expr[i+2])
            if float(int(tmp)) == tmp:
                tmp = int(tmp)
            expr[i:i+3] = [str(tmp)]
            continue #re evaluate at same point, in case of a ^ b ^ c
        i+=1

    # negative numbers
    i=0
    if expr[0] == "-":
        tmp = -float(expr[1])
        if float(int(tmp)) == tmp:
            tmp = int(tmp)
        expr[0:2] = [str(tmp)]
    while i < len(expr)-1:
        if expr[i+1] == "-":
            try:
                float(expr[i]) #if the previous is not a number, the next is a negative number
            except:
                tmp = -float(expr[i+2])
                if float(int(tmp)) == tmp:
                    tmp = int(tmp)
                expr[i+1:i+3] = [str(tmp)]
        i+=1
    
    # division/multiplication etc.
    i=0
    while i < len(expr)-1:
        if expr[i+1] == "*" or expr[i+1] == "/":
            if expr[i+1] == "*":
                tmp = float(expr[i])*float(expr[i+2])
            else:
                tmp = float(expr[i])/float(expr[i+2])
            if float(int(tmp)) == tmp:
                tmp = int(tmp)
            expr[i:i+3] = [str(tmp)]
            continue
        i+=1
    
    #addition/subtraction
    i=0
    while i < len(expr)-1:
        if expr[i+1] == "+" or expr[i+1] == "-":
            if expr[i+1] == "+":
                tmp = float(expr[i])+float(expr[i+2])
            else:
                tmp = float(expr[i])-float(expr[i+2])
            if float(int(tmp)) == tmp:
                tmp = int(tmp)
            expr[i:i+3] = [str(tmp)]
            continue
        i+=1

    #string concatenation
    i=0
    while i < len(expr)-1:
        if expr[i+1] == "&":
            #need to remove the closing quote mark of the first word
            #and the opening quote mark of the second word
            expr[i:i+3] = [expr[i][:-1] + expr[i+2][1:]]
            continue
        i+=1
    
    #comparisons
    i=0
    while i < len(expr)-1:
        if expr[i+1] in ["<", ">", "<=", ">=", "<>", "="]:
            operand = expr[i+1]
            a = float(expr[i])
            b = float(expr[i+2])
            c = False
            if operand == "<":
                c = a<b
            elif operand == ">":
                c = a>b
            elif operand == "<=":
                c = a<=b
            elif operand == ">=":
                c = a>=b
            elif operand == "<>":
                c = a!=b
            elif operand == "=":
                c = a==b
            expr[i:i+3] = ["TRUE" if c else "FALSE"]
            continue
        i+=1
    
    #logical NOT
    i=0
    while i < len(expr)-1:
        if expr[i] == "NOT":
            if expr[i+1] == "NOT":
                expr = expr[:i] + expr[i+2:]
                continue
            expr[i:i+2] = ["TRUE" if expr[i+1]=="FALSE" else "FALSE"]
        i+=1
    #logical AND
    i=0
    while i < len(expr)-1:
        if expr[i+1] == "AND":
            expr[i:i+3] = ["TRUE" if expr[i]=="TRUE" and expr[i+2]=="TRUE" else "FALSE"]
        i+=1
    #logical OR
    i=0
    while i < len(expr)-1:
        if expr[i+1] == "OR":
            expr[i:i+3] = ["TRUE" if expr[i]=="TRUE" or expr[i+2]=="TRUE" else "FALSE"]
        i+=1

    #a, ":", b into [a, b] or a TO b into [a, b]
    i=0
    while i < len(expr)-1:
        if expr[i+1] == ":" or expr[i+1] == "TO":
            expr[i:i+3] = [[expr[i], expr[i+2]]]
        i+=1

    return expr[0]

def interpret(line_num, local_vars=[], external_vars=[], references = {}, global_scope = False):
    endcase_idx_stack = [] #we must store the index for the next endcase at all times, so we can jump there immediately
    parsed_for_args = {}
    if global_scope:
        declared_vars = global_vars #automatic link because of "by assignment"
    else:
        declared_vars = global_vars | local_vars
    def strip(s):
        return s[1:-1] if s[0] == '"' or s[0] == "'" else s
    i = line_num
    while i < len(pseudocode):
        line = pseudocode[i]
        if line[0] == "INPUT":
            j = 1
            while j < len(line):
                if j == ",":
                    continue

                var_name = line[j]

                if j < len(line)-1 and line[j+1] == "[": #assigning to a value in an array
                    #linear search for closing
                    open_brackets = 1
                    close_idx = j+2
                    while open_brackets: #it suffices to only check for [ == ]
                        if line[close_idx] == "[":
                            open_brackets += 1
                        elif line[close_idx] == "]":
                            open_brackets -= 1 
                        close_idx+=1
                    index_array = evaluate(line[j+1:close_idx+1], declared_vars) #evaluate "[", "1", "]" into ["1"]
                    arr = declared_vars[var_name]
                    for idx in index_array[:-1]:
                        arr = arr[int(idx)-1] #iteratively access until you are 1 before the correct location
                    #python's native "by assignment", modfies declared_vars[var_name] successfully
                    if arr[int(index_array[-1])-1][0] == '"':
                        arr[int(index_array[-1])-1] = '"' + input() + '"'
                    elif arr[int(index_array[-1])-1][0] == "'":
                        arr[int(index_array[-1])-1] = "'" + input() + "'"
                    else:
                        arr[int(index_array[-1])-1] = input()
                    #arr is a deepcopy if it was passed in as a argument
                    #if it is a reference, it needs to be manually changed
                    
                    j = close_idx
                else: #base case, not inputting into array    
                    #do things depending on the type
                    if declared_vars[var_name][0] == '"':
                        declared_vars[var_name] = '"' + input() + '"'
                    elif declared_vars[var_name][0] == "'":
                        declared_vars[var_name] = "'" + input() + '"'
                    else:
                        declared_vars[var_name] = input()

                if var_name in references: #if the thing modified is a reference to something
                    #case 1: no arrays
                    #case 2: array passed by reference, arr[idx] modified
                    #case 3: arr[idx] passed by reference as var, var modified
                    ref = references[var_name]
                    #if ref is composed of [arr_name, [idx]], we can determine that it is case 3
                    #if ref is just a single name, we can just skip
                    #for case 2, just update the entire array
                    if type(ref) is list: #case 3:
                        arr_name, index_array = ref
                        #references come from external sources. Either external_vars or global_vars
                        arr = external_vars[arr_name]
                        #external_vars is an assignement to declared_vars of where this subprocess was called
                        #therefore it automatically updates when changed
                        #because declared_vars = global_vars | local_vars, and lists are always passed "by assignment",
                        #coincidentally, updating declared_vars[arr_name] updates global_vars[arr_name]
                        #therefore, it is sufficient to only update declared_vars[arr_name]
                        #which is referenced by external_vars
                        for idx in index_array[:-1]:
                            arr = arr[int(idx)-1] #array maintains the reference due to python "by assignment"
                        arr[int(index_array[-1])-1] = declared_vars[var_name]
                    else: #case 1, 2
                        if ref in global_vars:
                            global_vars[ref] = declared_vars[var_name]
                        external_vars[ref] = declared_vars[var_name]
                        #dereference and assign

                j+=1
        elif line[0] == "OUTPUT":
            cur = []
            open_brackets = 0
            for j in line[1:]:
                if j[-1] in "([":
                    open_brackets+=1
                elif j[-1] in ")]":
                    open_brackets-=1
                if open_brackets == 0 and j == ",":
                    print(strip(evaluate(cur, declared_vars)), end=" ")
                    cur = []
                else:
                    cur+=[j]
            print(strip(evaluate(cur, declared_vars)))
        
        elif line[0] == "DECLARE":
            #DECLARE var1, var2, var3 : ARRAY[...] OF TYPE
            if line[-2] == "OF": #ARRAY
                colon_idx = line.index(":")
                val_type = line[-1]
                open_idx = line.index("[")
                full_index_array = evaluate(line[open_idx:-2], declared_vars) #["[", "a", ":", "b", "]"]
                index_array = [i[1] for i in full_index_array] #only "b" matters, no support for a yet
                for j in line[1:colon_idx]: #for each var being delcared
                    declared_vars[j] = make_array(index_array, DEFAULT_VALS[val_type])
            else:
                #DECLARE var1, var2, var3 : TYPE
                for j in line[1:-2]:
                    declared_vars[j] = DEFAULT_VALS[line[-1]]

        #assignment
        elif len(line) >= 3 and line[1] == "<-":
            declared_vars[line[0]] = evaluate(line[2:], declared_vars)
            if line[0] in references:
                ref = references[line[0]]
                if type(ref) is list: #case 1, 3, defined line 503
                    arr_name, index_array = ref
                    arr = external_vars[arr_name]
                    for idx in index_array[:-1]:
                        arr = arr[int(idx)-1] #array maintains the reference due to python "by assignment"
                    arr[int(index_array[-1])-1] = declared_vars[line[0]]
                else:
                    if ref in global_vars:
                        global_vars[ref] = declared_vars[line[0]]
                    external_vars[ref] = declared_vars[line[0]]
        elif "<-" in line and line[1] == "[": #arr[i] <- val, <- will be at line[4] instead
            arrow_idx = line.index("<-")
            close_idx = arrow_idx - 1
            open_idx = line.index("[")
            index_array = evaluate(line[open_idx:close_idx+1], declared_vars)
            arr = declared_vars[line[0]]
            for j in index_array[:-1]: #repeatedly access index
                arr = arr[int(j)-1] #pseudocode is 1 indexed
            arr[int(index_array[-1])-1] = evaluate(line[arrow_idx+1:], declared_vars) #evaluate the thing right of <-
            if line[0] in references: #case 2, defined line 503
                ref = references[line[0]]
                if ref in global_vars:
                    global_vars[ref] = declared_vars[line[0]]
                external_vars[ref] = declared_vars[line[0]]
        elif line[0] == "IF":
            res = evaluate(line[1:-1], declared_vars) #IF condition ELSE
            if res == "FALSE":
                i = next_point[i] #jump to ELSE/ENDIF, for ELSE, because i+=1, ELSE won't be skipped
        elif line[0] == "ELSE": #Only possible if the IF successfully passed
            i = next_point[i] #skip the code for ELSE, jump to ENDIF

        elif line[0] == "WHILE": #WHILE condition DO
            if evaluate(line[1:-1], declared_vars) == "FALSE":
                i = next_point[i]
        elif line[0] == "ENDWHILE":
            i = loop_start[i]-1 #end up on WHILE afer i+=1

        elif line[0] == "FOR": #FOR i<-l TO r STEP step, should only happen once per for loop
            arrow_idx = line.index("<-")
            to_idx = line.index("TO")
            l = int(evaluate(line[arrow_idx+1:to_idx], declared_vars))
            step = 1 #default to 1 if step not found
            if "STEP" in line:
                step = int(evaluate(line[line.index("STEP")+1:], declared_vars))
                r = int(evaluate(line[to_idx+1:line.index("STEP")], declared_vars))
            else:
                r = int(evaluate(line[to_idx+1:], declared_vars))
            if (step > 0 and l > r) or (step < 0 and l < r): #skip from pre-condition
                i = next_point[i]
            declared_vars[line[1]] = str(l)
            parsed_for_args[i] = [l, r, step]
        elif line[0] == "NEXT":
            l, r, step = parsed_for_args[loop_start[i]]
            parsed_for_args[loop_start[i]][0] += step
            declared_vars[line[1]] = str(l+step) #update both
            if (step > 0 and l + step <= r) or (step < 0 and l + step >= r):
                i = loop_start[i]

        elif line[0] == "UNTIL":
            if evaluate(line[1:], declared_vars) == "FALSE":
                i = loop_start[i]

        elif line[0] == "CASE": #CASE OF var1
            val = evaluate(line[2:], declared_vars)
            endcase_idx_stack.append(next_point[i])
            i+=1
            #Edge case no. 1: CASE, OTHERWISE, ENDCASE
            if pseudocode[i][0] == "OTHERWISE":
                i+=1
                continue
            #Edge case no. 2: CASE, ENDCASE
            if pseudocode[i][0] == "ENDCASE":
                endcase_idx_stack.pop()
                i+=1
                continue
            while evaluate(pseudocode[i][:-1], declared_vars) != val: #evaluate left of :
                i = next_point[i]
                if pseudocode[i][0] in ["OTHERWISE", "ENDCASE"]:
                    endcase_idx_stack.pop()
                    break
        elif line[-1] == ":": #var 1 : statement, doesn't affect the : in declare etc.
            #should only happen if the previous passed successfully
            #jump straight to endcase
            i = endcase_idx_stack[-1]
            endcase_idx_stack.pop()

        elif line[0] == "RETURN":
            return evaluate(line[1:], declared_vars)
        elif line[0] == "CALL":
            evaluate(line[1:], declared_vars)
        elif line[0] == "ENDPROCEDURE":
            return
        
        elif line[0] in ["PROCEDURE", "FUNCTION"]: #PROCEDURE proc( arg1 : TYPE, arg2 : TYPE )
            args = []
            #proc( arg1 : TYPE, BYREF arg2 : TYPE, arg3, TYPE, BYVAL arg4 : TYPE, arg5 : TYPE)
            #should result in byval, byref, byref, byval, byval
            #rule: if unspecified, inherit byref/byval from the previous arg
            prev = "BYVAL"
            for j in range(len(line)-1):
                if line[j+1] == ":":
                    if line[j-1] in ["BYREF", "BYVAL"]:
                        prev = line[j-1]
                    args.append([prev,line[j]])
            
            subprocs[line[1][:-1]] = [i,args]
            i = next_point[i]
            
        i+=1

interpret(0, global_scope=True)
