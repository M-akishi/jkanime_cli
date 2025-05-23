from playwright.sync_api import sync_playwright
import shutil
import sys
import os
from InquirerPy import inquirer
import threading
import itertools
import time
import subprocess

BASE_URL = "https://jkanime.net"
BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def limpiar_consola():
    os.system("cls" if os.name == "nt" else "clear")

def mostrar_cargando(mensaje="Cargando"):
    done = threading.Event()

    def animacion():
        for c in itertools.cycle(['.', '..', '...']):
            if done.is_set():
                break
            sys.stdout.write(f'\r{mensaje}{c}   ')
            sys.stdout.flush()
            time.sleep(0.5)
        sys.stdout.write('\r' + ' ' * (len(mensaje) + 5) + '\r')

    t = threading.Thread(target=animacion)
    t.start()

    return done.set

def check_dependencies():
    ## Verificar que existan mpv y yt-dlp
    for dep in ["mpv", "yt-dlp"]:
        if not shutil.which(dep):
            print(f"[ERROR] No se encontró '{dep}' en el PATH.")
            print(f"Por favor instala '{dep}', por ejemplo usando: scoop install {dep}")
            sys.exit(1)
            
def crear_navegador_headless():
    ## Navegador Sin interfaz Firefox
    p = sync_playwright().start()
    firefox_path = os.path.join(BASE_PATH, ".local-browsers", "firefox-1482", "firefox", "firefox.exe")
    browser = p.firefox.launch(headless=True, executable_path=firefox_path)
    context = browser.new_context(user_agent="Mozilla/5.0")
    page = context.new_page()
    return p, browser, context, page

def buscar_series_jkanime(nombre):
    p, browser, context, page = crear_navegador_headless()
    resultados = []
    stop_animation = mostrar_cargando("buscando series")
    ## Tratar de hacer la busqueda, luego encontrar el contenedor de series y hacerlo lista
    try:
        url = f"{BASE_URL}/buscar/" + nombre.replace(" ", "%20")
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector("div.col-lg-12 > div.anime__page__content > div.row.page_directorio", timeout=10000)
        contenedor = page.query_selector("div.col-lg-12 > div.anime__page__content > div.row.page_directorio")
        animes = contenedor.query_selector_all("div.col-lg-2.col-md-6.col-sm-6")
        for a in animes:
            titulo = a.query_selector("h5 a").inner_text()
            href = a.query_selector("a").get_attribute("href")
            resultados.append({
                "titulo": titulo,
                "url": href,
            })
    except Exception as e:
        print(f"Error al buscar series en JKAnime: {e}")
    finally:
        stop_animation()
        browser.close()
        p.stop()
    return resultados

def obtener_episodios(url_serie, pagina=1):
    p, browser, context, page = crear_navegador_headless()
    episodios = []
    stop_animation = mostrar_cargando(f"Buscando episodios página {pagina}")
    try:
        url_pagina = f"{url_serie}{'#pag' + str(pagina) if pagina > 1 else ''}"
        page.goto(url_pagina, wait_until="domcontentloaded")
        page.wait_for_selector("div.col-lg-12.capitulos.animetab > div.row.col-12", timeout=10000)
        contenedor = page.query_selector("div.col-lg-12.capitulos.animetab > div.row.col-12")
        capitulos = contenedor.query_selector_all("div.epcontent.col-lg-3.col-md-4.col-sm-6.col-4")
        for a in capitulos:
            titulo = a.query_selector("span").inner_text()
            href = a.query_selector("a").get_attribute("href")
            episodios.append({
                "titulo": titulo,
                "url": href,
            })
    except Exception as e:
        print(f"Error al obtener los episodios: {e}")
    finally:
        stop_animation()
        browser.close()
        p.stop()
    return episodios

def menu_episodios(episodios, pagina, total_paginas):
    opciones = [ep['titulo'] for ep in episodios]
    
    # Agregar opciones de paginación y cancelar
    if pagina > 1:
        opciones.append("Página anterior")
    if pagina < total_paginas:
        opciones.append("Página siguiente")
    opciones.append("Cancelar")
    
    eleccion = inquirer.select(
        message=f"Elige un episodio (Página {pagina}/{total_paginas}):",
        choices=opciones
    ).execute()
    
    limpiar_consola()
    
    return eleccion

def reproducir_en_mpv(url):
    return 0

def obtener_link_mpv(url_episodio):
    return 0

def obtener_paginas(url_pagina):
    p, browser, context, page = crear_navegador_headless()
    stop_animation = mostrar_cargando("Buscando páginas")
    num_paginas = 1  # Por defecto al menos 1

    try:
        page.goto(url_pagina, wait_until="domcontentloaded")
        
        # Esperar que se cargue la lista de paginación visible
        page.wait_for_selector("div.anime_bar div.nice-select.anime__pagination ul.list", timeout=10000)
        
        # Obtener todos los elementos <li> de paginación
        items = page.query_selector_all("div.anime_bar div.nice-select.anime__pagination ul.list > li")
        num_paginas = len(items)

    except Exception as e:
        print(f"Error al obtener la cantidad de páginas: {e}")
    finally:
        stop_animation()
        browser.close()
        p.stop()
    
    return num_paginas


def reproducir_episodio(url_episodio):
    p, browser, context, page = crear_navegador_headless()

    m3u8_url = None

    def handle_request(route, request):
        nonlocal m3u8_url
        url = request.url
        if ".m3u8" in url:
            m3u8_url = url
        route.continue_()

    # Interceptar todas las solicitudes
    page.route("**/*", handle_request)

    page.goto(url_episodio, wait_until="networkidle")

    # Esperar un poco para que carguen los requests
    page.wait_for_timeout(3000)

    browser.close()
    p.stop()

    if m3u8_url:
        subprocess.run(["mpv", m3u8_url], check=True)
    else:
        print("No se encontró URL .m3u8")
    

def main():
    while True:
        nombre = input("\nIntroduce el nombre de la serie para buscar (o Enter para salir): ").strip()
        
        limpiar_consola()
        
        if not nombre:
            print("Saliendo del programa.")
            break

        resultados = buscar_series_jkanime(nombre)
        if not resultados:
            print("No se encontraron resultados.")
            continue

        eleccion = inquirer.select(
            message="Elije la serie:",
            choices=[serie['titulo'] for serie in resultados] + ["Cancelar"]
        ).execute()
        
        limpiar_consola()

        if eleccion == "Cancelar":
            continue

        serie_seleccionada = next((s for s in resultados if s['titulo'] == eleccion), None)
        url_serie = serie_seleccionada["url"]
        total_paginas = obtener_paginas(url_serie)
        pagina = 1

        while True:
            episodios = obtener_episodios(url_serie, pagina)
            eleccion = menu_episodios(episodios, pagina, total_paginas)

            if eleccion == "Cancelar":
                break
            elif eleccion == "Página siguiente" and pagina < total_paginas:
                pagina += 1
            elif eleccion == "Página anterior" and pagina > 1:
                pagina -= 1
            else:
                ep_seleccionado = next((ep for ep in episodios if ep['titulo'] == eleccion), None)
                if ep_seleccionado:
                    url_episodio = ep_seleccionado["url"]
                    print(f"Reproduciendo: {ep_seleccionado['titulo']}")
                    reproducir_episodio(url_episodio)
                    limpiar_consola()
                    break



        
if __name__ == "__main__":
    check_dependencies()
    main()
