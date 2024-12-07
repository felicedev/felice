import re
import sys
import os


class FeliceValue:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"{self.value}"


class FeliceClass:
    def __init__(self, name, properties):
        self.name = name
        self.properties = properties


class FeliceObject:
    def __init__(self, cls):
        self.cls = cls
        self.props = {}

    def set_prop(self, name, value):
        self.props[name] = value

    def get_prop(self, name):
        return self.props.get(name, FeliceValue(None))


class FeliceInterpreter:
    def __init__(self):
        self.variables = {}
        self.classes = {}
        self.objects = {}

    def run_file(self, filename):
        if not os.path.exists(filename):
            print("File non trovato:", filename)
            return
        with open(filename, 'r', encoding='utf-8') as f:
            code = f.read()
        self.run(code)

    def run(self, code):
        # Conserviamo tutte le linee
        self.lines = code.split('\n')
        # Rimuoviamo spazi di troppo alla fine
        # (Non tutti, perché ci servono per indentazione)
        self.lines = [line.rstrip() for line in self.lines if line.strip() != '']
        self.index = 0

        while self.index < len(self.lines):
            line = self.lines[self.index]
            self.index += 1
            self.execute_line(line)

    def execute_line(self, line, current_indent=0):
        line_stripped = line.strip()

        # Definizione classi
        if line_stripped.startswith("C'è una classe"):
            m = re.match(r"C'è una classe ([A-Za-z0-9_]+), ha:", line_stripped)
            if m:
                class_name = m.group(1)
                # Leggiamo le proprietà fino al punto finale
                properties = {}
                while self.index < len(self.lines):
                    pline = self.lines[self.index].strip()
                    self.index += 1
                    if pline.endswith('.'):
                        # ultima proprietà
                        pline = pline[:-1].strip()
                        if pline:
                            p = re.match(r"una proprietà ([A-Za-z0-9_]+) di ([A-Za-z0-9_]+)", pline)
                            if p:
                                prop_name = p.group(1)
                                prop_type = p.group(2)
                                properties[prop_name] = prop_type
                        break
                    else:
                        p = re.match(r"una proprietà ([A-Za-z0-9_]+) di ([A-Za-z0-9_]+)[,]?$", pline)
                        if p:
                            prop_name = p.group(1)
                            prop_type = p.group(2)
                            properties[prop_name] = prop_type
                self.classes[class_name] = FeliceClass(class_name, properties)
            return

        # Variabili
        var_match = re.match(r"C'è una variabile ([A-Za-z0-9_]+) di ([A-Za-z0-9_]+), vale (.+)\.$", line_stripped)
        if var_match:
            vname = var_match.group(1)
            vtype = var_match.group(2)
            val_str = var_match.group(3)
            val = self.evaluate_expression(val_str)
            self.variables[vname] = val
            return

        # Oggetti
        obj_match = re.match(r"C'è una ([A-Za-z0-9_]+) chiamata ([A-Za-z0-9_]+), ha:", line_stripped)
        if obj_match:
            class_name = obj_match.group(1)
            obj_name = obj_match.group(2)
            object_props = {}
            # Leggiamo proprietà fino al punto
            while self.index < len(self.lines):
                oline = self.lines[self.index].strip()
                self.index += 1
                end_obj = False
                if oline.endswith('.'):
                    end_obj = True
                    oline = oline[:-1].strip()
                if oline:
                    self.parse_object_prop_line(oline, object_props)
                if end_obj:
                    break
            obj = FeliceObject(self.classes[class_name])
            for k, v in object_props.items():
                obj.set_prop(k, v)
            self.objects[obj_name] = obj
            return

        # Assegnazioni
        assign_match = re.match(r"([A-Za-z0-9_ ]+( di [A-Za-z0-9_]+)?|[A-Za-z0-9_]+) è (.+)\.$", line_stripped)
        if assign_match:
            left = assign_match.group(1).strip()
            right = assign_match.group(3).strip()
            val = self.evaluate_expression(right)
            self.assign_value(left, val)
            return

        # Se ... allora:
        # Senza parentesi, e senza FineSe.
        se_match = re.match(r"Se (.+) allora:$", line_stripped)
        if se_match:
            cond_str = se_match.group(1).strip()
            cond_val = self.evaluate_condition(cond_str)
            true_block, false_block = self.read_if_block(current_indent)
            if cond_val:
                self.execute_block(true_block)
            else:
                self.execute_block(false_block)
            return

        # scrivi ... sulla console.
        write_match = re.match(r"scrivi (.+) sulla console\.$", line_stripped)
        if write_match:
            expr = write_match.group(1).strip()
            val = self.evaluate_expression(expr)
            print(val.value)
            return

        # Se nessun match, potrebbe essere un'istruzione vuota o non riconosciuta
        # La ignoriamo.
        return

    def read_if_block(self, current_indent=0):
        # Dopo un "Se ... allora:" leggiamo le linee indentate come blocco vero
        # Se troviamo un "Altrimenti:" allo stesso livello di indentazione, iniziamo il blocco falso
        # Quando troviamo una linea di indentazione minore o uguale e non "Altrimenti:",
        # o terminiamo il file, finisce il blocco condizionale.

        # Determiniamo l'indentazione del Se
        # Contiamo gli spazi a inizio riga di line già letta.
        # Ritorniamo due liste: true_block, false_block
        se_indent = self.get_line_indent(self.lines[self.index - 1])
        true_block = []
        false_block = []
        current_block = true_block

        while self.index < len(self.lines):
            line = self.lines[self.index]
            line_indent = self.get_line_indent(line)
            line_stripped = line.strip()

            # Se l'indentazione è minore o uguale a quella del Se e la linea non è Altrimenti:
            # significa che siamo usciti dal blocco if/else
            if line_indent <= se_indent and not line_stripped.startswith(
                    "Altrimenti:") and not line_stripped.startswith("Se "):
                break

            if line_stripped == "Altrimenti:" and line_indent == se_indent:
                # Passiamo al blocco falso
                current_block = false_block
                self.index += 1
                continue

            # Se siamo in un blocco (true o false), aggiungiamo la linea se indentata maggiore di se_indent
            if line_indent > se_indent:
                current_block.append(line)
                self.index += 1
            else:
                # se line_indent <= se_indent e non è "Altrimenti:", e non è un nuovo Se, blocco terminato
                break

        return true_block, false_block

    def execute_block(self, block_lines):
        i = 0
        while i < len(block_lines):
            line = block_lines[i]
            i += 1
            self.execute_line(line)

    def parse_object_prop_line(self, line, prop_dict):
        parts = [p.strip() for p in line.split(',')]
        for part in parts:
            if not part:
                continue
            pm = re.match(r"([A-Za-z0-9_]+) è (.+)$", part)
            if pm:
                pname = pm.group(1).strip()
                pval_str = pm.group(2).strip()
                pval = self.evaluate_expression(pval_str)
                prop_dict[pname] = pval

    def assign_value(self, left, val):
        dm = re.match(r"([A-Za-z0-9_]+) di ([A-Za-z0-9_]+)$", left)
        if dm:
            prop_name = dm.group(1)
            obj_name = dm.group(2)
            if obj_name in self.objects:
                self.objects[obj_name].set_prop(prop_name, val)
            else:
                raise Exception(f"Oggetto {obj_name} non trovato.")
        else:
            self.variables[left] = val

    def evaluate_condition(self, expr):
        # Gestisce espressioni tipo: "x è maggiore di soglia"
        # senza parentesi
        cond_match = re.match(r"(.+) è (maggiore|minore|uguale) di (.+)$", expr)
        if cond_match:
            lhs_str = cond_match.group(1).strip()
            mode = cond_match.group(2)
            rhs_str = cond_match.group(3).strip()
            lhs_val = self.evaluate_expression(lhs_str)
            rhs_val = self.evaluate_expression(rhs_str)

            if lhs_val.value is None or rhs_val.value is None:
                return False

            if mode == "maggiore":
                return lhs_val.value > rhs_val.value
            elif mode == "minore":
                return lhs_val.value < rhs_val.value
            elif mode == "uguale":
                return lhs_val.value == rhs_val.value

        return False

    def evaluate_expression(self, expr):
        expr = expr.strip()

        # stringa
        if expr.startswith('"') and expr.endswith('"'):
            return FeliceValue(expr[1:-1])

        # proprietà di oggetto: "nomeProp di nomeOggetto"
        dm = re.match(r"([A-Za-z0-9_]+) di ([A-Za-z0-9_]+)$", expr)
        if dm:
            prop_name = dm.group(1)
            obj_name = dm.group(2)
            if obj_name in self.objects:
                return self.objects[obj_name].get_prop(prop_name)
            else:
                return FeliceValue(None)

        # numero intero
        if re.match(r"^[0-9]+$", expr):
            return FeliceValue(int(expr))

        # decimale
        if re.match(r"^[0-9]+\.[0-9]+$", expr):
            return FeliceValue(float(expr))

        # booleani
        if expr == "vero":
            return FeliceValue(True)
        if expr == "falso":
            return FeliceValue(False)

        # variabile
        if expr in self.variables:
            return self.variables[expr]

        # operazioni aritmetiche semplici non tra parentesi non richieste qui
        # ci si può estendere se necessario

        return FeliceValue(None)

    def get_line_indent(self, line):
        # Conta il numero di spazi all'inizio della linea
        return len(line) - len(line.lstrip(' '))

# ESEMPIO DI ESECUZIONE:
# Supponendo di avere un file "esempio.fel" con il codice di esempio:
#
# interp = FeliceInterpreter()
# interp.run_file("esempio.fel")
#
# Dovrebbe stampare:
# "x è maggiore della soglia"
# "fine programma"
