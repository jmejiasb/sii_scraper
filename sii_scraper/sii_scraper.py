import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager


class SiiScraper: 
    def __init__(self, headless:bool = False):
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_experimental_option("detach", True)
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.fonts": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
        }
        options.add_experimental_option("prefs", prefs)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 20)

    def login_and_navigate(self):
        self.driver.get("https://zeusr.sii.cl//AUT2000/InicioAutenticacion/IngresoRutClave.html?https://misiir.sii.cl/cgi_misii/siihome.cgi")
        

        login_link = self.wait.until(EC.element_to_be_clickable((By.ID, "mienlace")))
        login_link.click()

        self.wait.until(EC.alert_is_present())

        alert = self.driver.switch_to.alert
        # print("Confirm text:", alert.text)
        alert.accept()

        services_menu = self.wait.until(
            EC.presence_of_element_located((By.LINK_TEXT, "Servicios online"))
        )

        actions = ActionChains(self.driver)
        actions.move_to_element(services_menu).click().perform()

        factura_link = self.wait.until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Factura electrónica"))
        )

        # 4) Click it
        factura_link.click()

        accordion_link = self.wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR,
            "p.accordion_special a[href='1039-3256.html']"
        )))

        # 2. Click it
        accordion_link.click()

        registro = self.wait.until(EC.element_to_be_clickable((
            By.LINK_TEXT,
            "Ingresar al Registro de Compras y Ventas"
        )))

        registro.click()

    def scrape_all(self) -> pd.DataFrame:
        try:
            self.login_and_navigate()

            self.wait.until(lambda d: len(
                d.find_elements(By.CSS_SELECTOR, "select[name='rut'] option")
            ) > 2)

            # Convertir esto a un for loop
            rut_select = self.wait.until(EC.element_to_be_clickable((By.NAME, "rut")))
            select = Select(rut_select)
            option_count = len(select.options)

            # ruts = [opt.text.strip() for opt in all_opts if opt.text.strip() and opt.text.strip() != "" and opt.text.strip() == "Empresa"]
            # print("Will iterate RUTs:", ruts)
            
            all_rows = []
            headers = [
                "type_purchase", "supplier_id", "supplier_name", "number", "date", "date_accepted", "type", "exent_total", "net_total", "iva", "other_tax", "iva_not", 
                "code_iva_not", "total", "total_activo", "iva_activo", "iva_comun", "tax_no_credit", "iva_no_retenido", "type_document_ref", "folio_ref",  
                "tabaco_puro", "tabaco_cigarrillos", "tabaco_elaborado", "nce_or_nde", "rut_holding"
            ]

            wait = WebDriverWait(self.driver, 2)

            for idx in range(1, option_count): 
                sel = Select(rut_select)
                sel.select_by_index(idx)  # index 0 = placeholder, 1 = first RUT, 2 = second RUT
                # time.sleep(5)

                rut_value = sel.first_selected_option.get_attribute("value")
                # (or use .text if you prefer the visible text)
                print(f"Obteniendo facturas para RUT {rut_value!r}")

                # 2) Click “Consultar”
                consult_btn = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "form[name='formContribuyente'] button[type='submit']"
                )

                consult_btn.click()

                try:
                    factura = wait.until(EC.element_to_be_clickable((
                        By.XPATH,
                        "//a[contains(text(),'Factura Electrónica') and @ui-sref]"
                    )))
                    factura.click()
                except:
                    print(f"→ No Factura Electrónica link for RUT {rut_value}, skipping.")
                    continue


                length_sel = wait.until(EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "select[name='tableCompra_length']"
                )))

                Select(length_sel).select_by_value("100")

                wait.until(lambda d: len(
                    d.find_elements(By.CSS_SELECTOR, "#tableCompra tbody tr")
                ) >= 1)

                # table = driver.find_element(By.ID, "tableCompra")

                # if headers is None:
                #     head_ths = self.driver.find_elements(
                #         By.CSS_SELECTOR,
                #         ".dataTables_scrollHeadInner table th div.dataTables_sizing"
                #     )
                #     headers = [th.text.strip() for th in head_ths]
                #     headers.append("RUT Seleccionado")

                # Extract rows
                for tr in self.driver.find_elements(By.CSS_SELECTOR, "#tableCompra tbody tr"):
                    tds = tr.find_elements(By.TAG_NAME, "td")

                    supplier_link = tds[1].find_element(By.TAG_NAME, "a")
                    supplier_id   = supplier_link.text.strip()
                    supplier_name = supplier_link.get_attribute("data-original-title")

                    row_values = [tds[0].text.strip()]                # type_purchase
                    row_values.append(supplier_id)                    # supplier_id
                    row_values.append(supplier_name)                  # supplier_name

                    # now the rest (shift your indices by –1 because you’ve already consumed tds[0] and tds[1])
                    for td in tds[2:]:
                        row_values.append(td.text.strip())

                    row_values.append(rut_value)  # tag them with the RUT we used
                    all_rows.append(row_values)

            if all_rows:
                df = pd.DataFrame(all_rows, columns=headers, dtype=str)
                # print(df.head())
                return df
        finally:
            self.driver.quit()