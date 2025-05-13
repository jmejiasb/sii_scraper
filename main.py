import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from pathlib import Path
import csv

def get_chrome_user_data_path() -> Path:
    """
    Returns the path to Chrome's User Data folder on Windows by using the LOCALAPPDATA env var.
    """
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise EnvironmentError("Could not find LOCALAPPDATA environment variable.")
    return Path(local_app_data) / "Google" / "Chrome" / "User Data"

def main():

    user_data_path = get_chrome_user_data_path()
    print(f"Using Chrome user data at: {user_data_path}")

    options = Options()
    # options.add_argument("--headless=new")
    # options.add_argument(f"--user-data-dir={user_data_path}")
    # options.add_argument(f"--profile-directory=Default"
    options.add_experimental_option("detach", True)

    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try: 
        print("trying to driver.get")
        driver.get("https://zeusr.sii.cl//AUT2000/InicioAutenticacion/IngresoRutClave.html?https://misiir.sii.cl/cgi_misii/siihome.cgi")

        wait = WebDriverWait(driver, 30)

        login_link = wait.until(EC.element_to_be_clickable((By.ID, "mienlace")))
        login_link.click()

        wait.until(EC.alert_is_present())

        alert = driver.switch_to.alert
        print("Confirm text:", alert.text)
        alert.accept()

        services_menu = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Servicios online"))
        )

        actions = ActionChains(driver)
        actions.move_to_element(services_menu).click().perform()

        factura_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Factura electrónica"))
        )

        # 4) Click it
        factura_link.click()

        accordion_link = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR,
            "p.accordion_special a[href='1039-3256.html']"
        )))

        # 2. Click it
        accordion_link.click()

        registro = wait.until(EC.element_to_be_clickable((
            By.LINK_TEXT,
            "Ingresar al Registro de Compras y Ventas"
        )))

        registro.click()

        # Convertir esto a un for loop
        rut_select = wait.until(EC.element_to_be_clickable((By.NAME, "rut")))

        all_opts = rut_select.find_elements(By.TAG_NAME, "option")
        ruts = [o.get_attribute("value") for o in all_opts if o.get_attribute("value").strip()]
        print("Will iterate RUTs:", ruts)
        
        all_rows = []
        headers = None

        for rut in ruts: 
            sel = Select(rut_select)
            sel.select_by_value(rut)  # index 0 = placeholder, 1 = first RUT, 2 = second RUT
            # time.sleep(5)
            # 2) Click “Consultar”
            consult_btn = driver.find_element(
                By.CSS_SELECTOR,
                "form[name='formContribuyente'] button[type='submit']"
            )

            consult_btn.click()

            try:
                factura = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((
                    By.XPATH,
                    "//a[contains(text(),'Factura Electrónica') and @ui-sref]"
                )))
                factura.click()
            except:
                print(f"→ No Factura Electrónica link for RUT {rut}, skipping.")
                continue


            length_sel = wait.until(EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "select[name='tableCompra_length']"
            )))

            Select(length_sel).select_by_value("100")

            wait.until(lambda d: len(
                d.find_elements(By.CSS_SELECTOR, "#tableCompra tbody tr")
            ) >= 1)

            table = driver.find_element(By.ID, "tableCompra")

            if headers is None:
                head_ths = driver.find_elements(
                    By.CSS_SELECTOR,
                    ".dataTables_scrollHeadInner table th div.dataTables_sizing"
                )
                headers = [th.text.strip() for th in head_ths]
                headers.append("RUT Seleccionado")

            # Extract rows
            for tr in driver.find_elements(By.CSS_SELECTOR, "#tableCompra tbody tr"):
                cells = [td.text.strip() for td in tr.find_elements(By.TAG_NAME, "td")]
                cells.append(rut)  # tag them with the RUT we used
                all_rows.append(cells)
                
        if all_rows:
            # write CSV
            with open("compras.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(all_rows)

        print("Saved compras.csv")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()

