import tkinter as tk
from tkinter import ttk, messagebox
import math
import bisect
import heapq
from itertools import count

# Series comerciales normalizadas:
# E12 se usa habitualmente para resistencias de 10 %.
# E96 se usa habitualmente para resistencias de 1 %.
E12 = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82]
E96 = [
    100, 102, 105, 107, 110, 113, 115, 118, 121, 124, 127, 130,
    133, 137, 140, 143, 147, 150, 154, 158, 162, 165, 169, 174,
    178, 182, 187, 191, 196, 200, 205, 210, 215, 221, 226, 232,
    237, 243, 249, 255, 261, 267, 274, 280, 287, 294, 301, 309,
    316, 324, 332, 340, 348, 357, 365, 374, 383, 392, 402, 412,
    422, 432, 442, 453, 464, 475, 487, 499, 511, 523, 536, 549,
    562, 576, 590, 604, 619, 634, 649, 665, 681, 698, 715, 732,
    750, 768, 787, 806, 825, 845, 866, 887, 909, 931, 953, 976
]

# Rango comercial que el programa considera:
# de 0.1 ohmios hasta 100 megaohmios.
MIN_RESISTENCIA = 0.1
MAX_RESISTENCIA = 100_000_000


def fmt_resistencia(valor):
    """Convierte un valor numérico a una cadena con Ω, kΩ o MΩ."""
    if valor >= 1_000_000:
        return f"{valor / 1_000_000:.6g} MΩ"
    if valor >= 1000:
        return f"{valor / 1000:.6g} kΩ"
    return f"{valor:.6g} Ω"


def generar_valores_comerciales(tolerancia):
    """
    Genera los valores nominales E12 o E96 entre 0.1 Ω y 100 MΩ.
    Los números E12 (10...82) y E96 (100...976) tienen escalas distintas.
    """
    if tolerancia == 10:
        base = E12
        divisor = 10
    else:
        base = E96
        divisor = 100

    valores = set()
    # Décadas de 0.1 Ω hasta 100 MΩ.
    for decada in range(-1, 9 + 1):
        factor = 10 ** decada / divisor
        for numero in base:
            valor = numero * factor
            if MIN_RESISTENCIA <= valor <= MAX_RESISTENCIA:
                valores.add(float(valor))
    return sorted(valores)


def paralelo(valores):
    """Calcula la resistencia equivalente de una lista en paralelo."""
    return 1.0 / sum(1.0 / r for r in valores)


def error_porcentual(valor, objetivo):
    return abs(valor - objetivo) / objetivo * 100.0


def vecinos_comerciales(valores, ideal, cantidad_lado=2):
    """
    Devuelve valores comerciales cercanos al valor ideal.
    Para una función monotónica, los más cercanos al ideal producen
    los equivalentes más cercanos al objetivo para el par fijado.
    """
    if not math.isfinite(ideal):
        return []
    pos = bisect.bisect_left(valores, ideal)
    inicio = max(0, pos - cantidad_lado)
    fin = min(len(valores), pos + cantidad_lado + 1)
    return valores[inicio:fin]


def buscar_combinaciones(objetivo, tolerancia, max_componentes, limite_resultados=100):
    """
    Busca los resultados más próximos con 1, 2 o 3 resistencias comerciales.

    En vez de crear una lista gigantesca con cada triple posible, fija cada
    pareja comercial y calcula matemáticamente qué tercera resistencia
    aproximaría mejor al objetivo. Luego busca los valores comerciales
    inmediatamente anteriores y posteriores a ese valor ideal.
    Así se cubren las topologías serie/paralelo de hasta tres resistencias
    de forma eficiente en el rango comercial definido arriba.
    """
    comerciales = generar_valores_comerciales(tolerancia)
    if not comerciales:
        return []

    resultados_heap = []
    secuencia = count()
    max_candidatos = max(2000, limite_resultados * 20)

    def guardar(valor, resistencias, topologia, descripcion):
        if not math.isfinite(valor) or valor <= 0:
            return
        error = error_porcentual(valor, objetivo)
        item = {
            "valor": valor,
            "resistencias": resistencias,
            "descripcion": descripcion,
            "componentes": len(resistencias),
            "topologia": topologia,
            "error": error
        }
        # El heap conserva candidatos de menor error. El elemento en la raíz
        # es el peor de los candidatos guardados.
        entrada = (-error, next(secuencia), item)
        if len(resultados_heap) < max_candidatos:
            heapq.heappush(resultados_heap, entrada)
        elif error < -resultados_heap[0][0]:
            heapq.heapreplace(resultados_heap, entrada)

    # Una resistencia: se consideran todos los valores comerciales.
    for r in comerciales:
        guardar(r, (r,), "Individual", fmt_resistencia(r))

    # Dos resistencias: se recorre cada primera resistencia y se calcula
    # la segunda ideal para serie y paralelo.
    if max_componentes >= 2:
        for a in comerciales:
            # Serie: a + b = objetivo -> b = objetivo - a
            ideal = objetivo - a
            for b in vecinos_comerciales(comerciales, ideal):
                guardar(a + b, (a, b), "Serie",
                        f"{fmt_resistencia(a)} + {fmt_resistencia(b)}")

            # Paralelo: 1/objetivo = 1/a + 1/b
            denominador = (1.0 / objetivo) - (1.0 / a)
            if denominador > 0:
                ideal = 1.0 / denominador
                for b in vecinos_comerciales(comerciales, ideal):
                    guardar(paralelo([a, b]), (a, b), "Paralelo",
                            f"{fmt_resistencia(a)} ∥ {fmt_resistencia(b)}")

    # Tres resistencias. Para cada pareja (a,b), calculamos la tercera
    # resistencia ideal para cada topología serie/paralelo de dos niveles.
    if max_componentes >= 3:
        n = len(comerciales)
        for i, a in enumerate(comerciales):
            for j in range(i, n):
                b = comerciales[j]

                # 1) Las tres en serie: a + b + c = objetivo.
                ideal = objetivo - a - b
                for c in vecinos_comerciales(comerciales, ideal):
                    guardar(a + b + c, (a, b, c), "Tres en serie",
                            f"{fmt_resistencia(a)} + {fmt_resistencia(b)} + {fmt_resistencia(c)}")

                # 2) Las tres en paralelo.
                denominador = (1.0 / objetivo) - (1.0 / a) - (1.0 / b)
                if denominador > 0:
                    ideal = 1.0 / denominador
                    for c in vecinos_comerciales(comerciales, ideal):
                        guardar(paralelo([a, b, c]), (a, b, c), "Tres en paralelo",
                                f"{fmt_resistencia(a)} ∥ {fmt_resistencia(b)} ∥ {fmt_resistencia(c)}")

                # 3) (a + b) en paralelo con c.
                suma = a + b
                denominador = (1.0 / objetivo) - (1.0 / suma)
                if denominador > 0:
                    ideal = 1.0 / denominador
                    for c in vecinos_comerciales(comerciales, ideal):
                        guardar(paralelo([suma, c]), (a, b, c), "Serie-paralelo",
                                f"({fmt_resistencia(a)} + {fmt_resistencia(b)}) ∥ {fmt_resistencia(c)}")

                # 4) (a en paralelo con b) en serie con c.
                ideal = objetivo - paralelo([a, b])
                for c in vecinos_comerciales(comerciales, ideal):
                    guardar(paralelo([a, b]) + c, (a, b, c), "Paralelo-serie",
                            f"({fmt_resistencia(a)} ∥ {fmt_resistencia(b)}) + {fmt_resistencia(c)}")

    # Ordena por error, después por número de componentes.
    candidatos = [entrada[2] for entrada in resultados_heap]
    candidatos.sort(key=lambda x: (x["error"], x["componentes"]))

    # Elimina resultados repetidos por misma topología, valor equivalente
    # y descripción; conserva hasta el límite solicitado.
    finales = []
    vistos = set()
    for item in candidatos:
        clave = (round(item["valor"], 9), item["topologia"], item["descripcion"])
        if clave in vistos:
            continue
        vistos.add(clave)
        finales.append(item)
        if len(finales) >= limite_resultados:
            break
    return finales


class CalculadoraResistencias:
    def __init__(self, root):
        self.root = root
        self.root.title("OhmLab | Calculadora de resistencias")
        self.root.geometry("1120x720")
        self.root.minsize(900, 600)
        self.root.configure(bg="#0b1220")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview", background="#111c30", foreground="#e7eef9",
            fieldbackground="#111c30", rowheight=30, borderwidth=0,
            font=("Segoe UI", 10)
        )
        style.configure(
            "Treeview.Heading", background="#1e3150", foreground="#ffffff",
            font=("Segoe UI", 10, "bold"), relief="flat"
        )
        style.map("Treeview", background=[("selected", "#2457a7")])
        style.configure("TCombobox", padding=6)

        header = tk.Frame(root, bg="#111c30", padx=28, pady=20)
        header.pack(fill="x")
        tk.Label(
            header, text="OhmLab", bg="#111c30", fg="#62d6c7",
            font=("Segoe UI", 25, "bold")
        ).pack(anchor="w")
        tk.Label(
            header,
            text="BUSCADOR DE VALORES COMERCIALES · REDES DE 1 A 3 RESISTENCIAS",
            bg="#111c30", fg="#a9bad3", font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(root, bg="#0b1220", padx=28, pady=20)
        body.pack(fill="both", expand=True)

        panel = tk.Frame(body, bg="#152239", padx=18, pady=18)
        panel.pack(fill="x")
        tk.Label(
            panel, text="Configura tu búsqueda", bg="#152239", fg="#ffffff",
            font=("Segoe UI", 13, "bold")
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 14))

        tk.Label(
            panel, text="Resistencia deseada (Ω)", bg="#152239", fg="#bdcbe0",
            font=("Segoe UI", 10)
        ).grid(row=1, column=0, sticky="w")
        self.objetivo = tk.Entry(
            panel, font=("Segoe UI", 12), width=18, bg="#0b1220",
            fg="#ffffff", insertbackground="white", relief="flat"
        )
        self.objetivo.insert(0, "100000")
        self.objetivo.grid(row=2, column=0, padx=(0, 18), ipady=8, sticky="ew")

        tk.Label(
            panel, text="Tolerancia comercial", bg="#152239", fg="#bdcbe0",
            font=("Segoe UI", 10)
        ).grid(row=1, column=1, sticky="w")
        self.tolerancia = ttk.Combobox(
            panel, values=["10 % (E12)", "1 % (E96)"],
            state="readonly", width=16, font=("Segoe UI", 11)
        )
        self.tolerancia.current(0)
        self.tolerancia.grid(row=2, column=1, padx=(0, 18), ipady=5, sticky="ew")

        tk.Label(
            panel, text="Máximo de resistencias", bg="#152239", fg="#bdcbe0",
            font=("Segoe UI", 10)
        ).grid(row=1, column=2, sticky="w")
        self.cantidad = ttk.Combobox(
            panel, values=["1", "2", "3"],
            state="readonly", width=8, font=("Segoe UI", 11)
        )
        self.cantidad.current(2)
        self.cantidad.grid(row=2, column=2, padx=(0, 18), ipady=5, sticky="ew")

        boton = tk.Button(
            panel, text="BUSCAR COMBINACIONES", command=self.buscar,
            bg="#35c8b5", fg="#07151e", activebackground="#70e5d5",
            activeforeground="#07151e", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2", padx=14, pady=11
        )
        boton.grid(row=2, column=3, sticky="ew")

        for col in range(4):
            panel.grid_columnconfigure(col, weight=1)

        self.estado = tk.Label(
            body, text="Ingresa un valor para comenzar.",
            bg="#0b1220", fg="#a9bad3", font=("Segoe UI", 10), anchor="w"
        )
        self.estado.pack(fill="x", pady=(14, 10))

        table_frame = tk.Frame(body, bg="#0b1220")
        table_frame.pack(fill="both", expand=True)

        columnas = ("pos", "equiv", "error", "tipo", "componentes")
        self.tabla = ttk.Treeview(table_frame, columns=columnas, show="headings")
        self.tabla.heading("pos", text="#")
        self.tabla.heading("equiv", text="VALOR EQUIVALENTE")
        self.tabla.heading("error", text="ERROR (%)")
        self.tabla.heading("tipo", text="CONEXIÓN")
        self.tabla.heading("componentes", text="COMBINACIÓN")
        self.tabla.column("pos", width=45, anchor="center")
        self.tabla.column("equiv", width=160, anchor="center")
        self.tabla.column("error", width=130, anchor="center")
        self.tabla.column("tipo", width=145, anchor="center")
        self.tabla.column("componentes", width=500, anchor="w")

        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll_y.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        footer = tk.Label(
            root,
            text="Serie: Req = R1 + R2 + ...     |     Paralelo: 1/Req = 1/R1 + 1/R2 + ...",
            bg="#111c30", fg="#8ea4c2", font=("Segoe UI", 9), pady=12
        )
        footer.pack(fill="x", side="bottom")

        self.buscar()

    def buscar(self):
        try:
            objetivo = float(self.objetivo.get().strip().replace(",", "."))
            if not math.isfinite(objetivo) or objetivo <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Valor no válido",
                "Escribe una resistencia positiva, por ejemplo 100000."
            )
            return

        tolerancia = 10 if self.tolerancia.get().startswith("10") else 1
        max_componentes = int(self.cantidad.get())

        self.estado.config(text="Calculando combinaciones…", fg="#62d6c7")
        self.root.update_idletasks()

        resultados = buscar_combinaciones(objetivo, tolerancia, max_componentes)

        for fila in self.tabla.get_children():
            self.tabla.delete(fila)

        for i, item in enumerate(resultados, start=1):
            self.tabla.insert(
                "", "end",
                values=(
                    i,
                    fmt_resistencia(item["valor"]),
                    f'{item["error"]:.6f} %',
                    item["topologia"],
                    item["descripcion"]
                )
            )

        if resultados:
            mejor = resultados[0]
            self.estado.config(
                text=(
                    f"Mejor resultado encontrado: {fmt_resistencia(mejor['valor'])}  |  "
                    f"Error: {mejor['error']:.6f} %  |  "
                    f"Se muestran hasta {len(resultados)} resultados cercanos."
                ),
                fg="#62d6c7"
            )
        else:
            self.estado.config(text="No se encontraron combinaciones.", fg="#ffb4a9")


if __name__ == "__main__":
    ventana = tk.Tk()
    app = CalculadoraResistencias(ventana)
    ventana.mainloop()
