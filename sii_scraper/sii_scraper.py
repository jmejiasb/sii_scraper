import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException


class SiiScraper: 
    def __init__(self, user: str, pwd: str, headless:bool = False):
        options = Options()

        self.user = user
        self.pwd = pwd

        if headless:
            options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")               # recommended for Linux
        options.add_argument("--no-sandbox")                # recommended in many CI systems
        options.add_argument("--disable-dev-shm-usage")  
        
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.fonts": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
        }
        options.add_experimental_option("prefs", prefs)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 30)

    def login_and_navigate(self):
        self.driver.get("https://zeusr.sii.cl//AUT2000/InicioAutenticacion/IngresoRutClave.html?https://misiir.sii.cl/cgi_misii/siihome.cgi")
        
        attempt = 1
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                login_link = WebDriverWait(self.driver, self.wait._timeout).until(
                    EC.element_to_be_clickable((By.ID, "myHref"))
                )
                # scroll into view just in case
                login_link.click()
                break  # success — exit the function
            except TimeoutException:
                print(f"→ Attempt {attempt}/{max_retries} to click login_link timed out.")
                if attempt < max_retries:
                    time.sleep(1)  # give it a moment before retrying
                else:
                    raise

        # self.wait.until(EC.alert_is_present())

        # alert = self.driver.switch_to.alert
        # # print("Confirm text:", alert.text)
        # alert.accept()

        run_input = self.wait.until(
            EC.element_to_be_clickable((By.ID, "uname"))
        )
        run_input.clear()
        run_input.send_keys(self.user)

        pwd_input = self.wait.until(
            EC.element_to_be_clickable((By.ID, "pword"))
        )
        pwd_input.clear()
        pwd_input.send_keys(self.pwd)

        submit_btn = self.wait.until(
            EC.element_to_be_clickable((By.ID, "login-submit"))
        )
        submit_btn.click()

        services_menu = self.wait.until(
            EC.presence_of_element_located((By.LINK_TEXT, "Servicios online"))
        )
        print("Menu servicios online")

        actions = ActionChains(self.driver)
        actions.move_to_element(services_menu).click().perform()

        factura_link = self.wait.until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Factura electrónica"))
        )
        print("Menu factura electronica")

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

        print("Ingresando al registro de compras y ventas")

    def _scrape_pending(self, wait, link_xpath: str, status: str, doc_type: str, rut_value: str, all_rows: list):
        
        try:
            link_el = wait.until(
                EC.element_to_be_clickable((By.XPATH, link_xpath))
            )
        except:
            print(f"→ No {status} - {doc_type} link for RUT {rut_value}, skipping.")
            return
        
        try:
            count_td = link_el.find_element(
                By.XPATH,
                ".//ancestor::td/following-sibling::td[1]"
            )
            # strip dots and parse
            count = int(count_td.text.replace(".", "").strip() or 0)
        except (NoSuchElementException, ValueError):
            print(f"→ Couldn't read count next to {doc_type} for RUT {rut_value}, skipping.")
            return
        
        if count <= 0:
            print(f"→ {doc_type} count is {count} for RUT {rut_value}, not scraping.")
            return
        
        for attempt in range(2):
            try:
                # ensure no leftover backdrops
                wait.until(EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, "div.modal-backdrop")
                ))
                # scroll into view then click
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", link_el)
                link_el.click()
                break
            except ElementClickInterceptedException:
                print("→ Click intercepted by backdrop, retrying…")
                # try to dismiss any open alert-modal
                try:
                    modal = self.driver.find_element(By.ID, "alert-modal")
                    modal.find_element(By.CSS_SELECTOR, ".modal-footer .btn-danger").click()
                except NoSuchElementException:
                    pass
                # then wait a moment for backdrop to disappear
                wait.until(EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, "div.modal-backdrop")
                ))
        else:
            print(f"→ Failed to click {doc_type} after retry, skipping.")
            return
        
        length_sel = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "select[name='tableCompra_length']"))
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", length_sel)
        length_sel = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "select[name='tableCompra_length']"))
        )
        Select(length_sel).select_by_value("100")    

        for tr in self.driver.find_elements(By.CSS_SELECTOR, "#tableCompra tbody tr"):
            
            tds = tr.find_elements(By.TAG_NAME, "td")

            supplier_link = ""
            try:
                supplier_link = tds[1].find_element(By.TAG_NAME, "a")
            except NoSuchElementException:
                supplier_link = tds[2].find_element(By.TAG_NAME, "a")
                
            supplier_id   = supplier_link.text.strip()
            supplier_name = supplier_link.get_attribute("data-original-title")

            row = []

            if (doc_type == "credit_note"):
                row = [
                    tds[0].text.strip(),
                    supplier_id,
                    supplier_name,
                    *[td.text.strip() for td in tds[2:6]],
                    "",
                    *[td.text.strip() for td in tds[6:-1]],
                    0,
                    0,
                    0,
                    tds[-1].text.strip(),
                    rut_value, 
                    status,
                    doc_type
                ]

                print(row)
            
            else:

                row = [
                    tds[1].text.strip(),
                    supplier_id,
                    supplier_name,
                    *[td.text.strip() for td in tds[3:7]],
                    "",
                    *[td.text.strip() for td in tds[7:-1]],
                    0,
                    0,
                    0,
                    tds[-1].text.strip(),
                    rut_value, 
                    status,
                    doc_type
                ]

            all_rows.append(row)


        volver_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[ng-click='doTheBack()']"))
        )
        volver_btn.click()

    def _scrape_section(self, wait, link_xpath: str, status: str, doc_type: str, rut_value: str, all_rows: list):
        """
        Clicks the link identified by link_xpath, scrapes all rows into all_rows
        tagging them with (rut_value, status, doc_type), then clicks “Volver” to go back.
        """

        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, link_xpath)))
            btn.click()
        except:
            print(f"→No {status} - {doc_type} link for RUT {rut_value}, skipping.")
            return

        length_sel = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "select[name='tableCompra_length']"))
        )

        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", length_sel)

        length_sel = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "select[name='tableCompra_length']"))
        )

        Select(length_sel).select_by_value("100")

        wait.until(lambda d: len(
            d.find_elements(By.CSS_SELECTOR, "#tableCompra tbody tr")
        ) >= 1)

        for tr in self.driver.find_elements(By.CSS_SELECTOR, "#tableCompra tbody tr"):
            
            tds = tr.find_elements(By.TAG_NAME, "td")

            supplier_link = tds[1].find_element(By.TAG_NAME, "a")
            supplier_id   = supplier_link.text.strip()
            supplier_name = supplier_link.get_attribute("data-original-title")

            # row_values = [data_cells[0].text.strip()]                # type_purchase
            row = []

            row = [
                tds[0].text.strip(),
                supplier_id,
                supplier_name,
                *[td.text.strip() for td in tds[2:]],
                rut_value, 
                status,
                doc_type
            ]

            all_rows.append(row)

        volver_btn = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[ng-click='doTheBack()']")
            )
        )

        volver_btn.click()

    def _click_pendientes(self):
        """
        Wait for the “Pendientes” tab to be clickable, then click it.
        """

        self.wait.until(
            EC.invisibility_of_element_located((By.ID, "esperaDialog"))
        )

        pendientes_locator = (
            By.XPATH,
            "//a[@ui-sref='compraPendiente' and normalize-space(strong/text())='Pendientes']"
        )

        elem = self.wait.until(EC.presence_of_element_located(pendientes_locator))
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
        
        self.wait.until(EC.element_to_be_clickable(pendientes_locator))
        try:
            elem.click()
        except ElementClickInterceptedException:
            print("→ click intercepted—falling back to JS click")
            self.driver.execute_script("arguments[0].click();", elem)

        self.wait.until(
            EC.invisibility_of_element_located((By.ID, "esperaDialog"))
        )

    def scrape_all(self) -> pd.DataFrame:
        try:
            self.login_and_navigate()

            try: 
                self.wait.until(lambda d: len(
                    d.find_elements(By.CSS_SELECTOR, "select[name='rut'] option")
                ) > 2)

            except TimeoutException:
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
                "tabaco_puro", "tabaco_cigarrillos", "tabaco_elaborado", "nce_or_nde", "rut_holding", "status", "doc_type"
            ]

            wait = WebDriverWait(self.driver, 2)

            # periodoMes = self.wait.until(EC.element_to_be_clickable((By.ID, "periodoMes")))
            # month_sel = Select(periodoMes)
            # month_sel.select_by_value("05")

            for idx in range(1, option_count): 
                sel = Select(rut_select)
                sel.select_by_index(idx)  # index 0 = placeholder, 1 = first RUT, 2 = second RUT
                # time.sleep(5)

                rut_value = sel.first_selected_option.get_attribute("value")
                # (or use .text if you prefer the visible text)
                print(f"Obteniendo facturas para RUT {rut_value!r}")

                self.wait.until(
                    EC.invisibility_of_element_located((By.ID, "esperaDialog"))
                )

                # 2) Click “Consultar”
                consult_btn = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "form[name='formContribuyente'] button[type='submit']"
                )

                try:
                    consult_btn.click()
                except ElementClickInterceptedException:
                    self.driver.execute_script("arguments[0].click();", consult_btn)

                self._scrape_section(
                    wait,
                    "//a[contains(text(),'Factura Electrónica') and @ui-sref]",
                    status="accepted",
                    doc_type="invoice",
                    rut_value=rut_value,
                    all_rows=all_rows
                )

                self._scrape_section(
                    wait,
                    "//a[contains(text(),'Factura no Afecta o Exenta Electrónica') and @ui-sref]",
                    status="accepted_exempt",
                    doc_type="invoice",
                    rut_value=rut_value,
                    all_rows=all_rows
                )
                
                self._scrape_section(
                    wait,
                    "//a[contains(text(),'Nota de Crédito Electrónica') and @ui-sref]",
                    status="accepted",
                    doc_type="credit_note",
                    rut_value=rut_value,
                    all_rows=all_rows
                )

                self._click_pendientes()

                try:
                    wait.until(EC.presence_of_element_located(
                        (By.XPATH, "//td[@ng-if=\"(row.rsmnLink)\"]")
                    ))
                except TimeoutException:
                    print(f"→ No pending‐documents table for RUT {rut_value}, skipping.")
                    continue

                self._scrape_pending(
                    wait,
                     "//a[@ui-sref and contains(normalize-space(.), 'Factura Electrónica')]",
                    status="pending",
                    doc_type="invoice",
                    rut_value=rut_value,
                    all_rows=all_rows,
                )

                self._scrape_pending(
                    wait,
                    "//a[@ui-sref and contains(normalize-space(.), 'Factura no Afecta o Exenta Electrónica')]",
                    status="pending_exempt",
                    doc_type="invoice",
                    rut_value=rut_value,
                    all_rows=all_rows,
                )

                self._scrape_pending(
                    wait,
                    "//a[@ui-sref and contains(normalize-space(.), 'Nota de Crédito Electrónica')]",
                    status="pending",
                    doc_type="credit_note",
                    rut_value=rut_value,
                    all_rows=all_rows,
                )

            if all_rows:
                df = pd.DataFrame(all_rows, columns=headers, dtype=str)
                # print(df.head())
                return df
        finally:
            self.driver.quit()

    def scrape_one(self, rut) -> pd.DataFrame: 

        try:
            self.login_and_navigate()

            try: 
                self.wait.until(lambda d: len(
                    d.find_elements(By.CSS_SELECTOR, "select[name='rut'] option")
                ) > 2)

            except TimeoutException:
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
                "tabaco_puro", "tabaco_cigarrillos", "tabaco_elaborado", "nce_or_nde", "rut_holding", "status", "doc_type"
            ]

            wait = WebDriverWait(self.driver, 2)

            # periodoMes = self.wait.until(EC.element_to_be_clickable((By.ID, "periodoMes")))
            # month_sel = Select(periodoMes)
            # month_sel.select_by_value("05")

            sel = Select(rut_select)
            sel.select_by_value(rut)  # index 0 = placeholder, 1 = first RUT, 2 = second RUT
            # time.sleep(5)

            rut_value = sel.first_selected_option.get_attribute("value")
            # (or use .text if you prefer the visible text)
            print(f"Obteniendo facturas para RUT {rut_value!r}")

            self.wait.until(
                EC.invisibility_of_element_located((By.ID, "esperaDialog"))
            )

            # 2) Click “Consultar”
            consult_btn = self.driver.find_element(
                By.CSS_SELECTOR,
                "form[name='formContribuyente'] button[type='submit']"
            )

            try:
                consult_btn.click()
            except ElementClickInterceptedException:
                self.driver.execute_script("arguments[0].click();", consult_btn)

            self._scrape_section(
                wait,
                "//a[contains(text(),'Factura Electrónica') and @ui-sref]",
                status="accepted",
                doc_type="invoice",
                rut_value=rut_value,
                all_rows=all_rows
            )

            self._scrape_section(
                wait,
                "//a[contains(text(),'Factura no Afecta o Exenta Electrónica') and @ui-sref]",
                status="accepted_exempt",
                doc_type="invoice",
                rut_value=rut_value,
                all_rows=all_rows
            )
            
            self._scrape_section(
                wait,
                "//a[contains(text(),'Nota de Crédito Electrónica') and @ui-sref]",
                status="accepted",
                doc_type="credit_note",
                rut_value=rut_value,
                all_rows=all_rows
            )

            self._click_pendientes()

            try:
                wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//td[@ng-if=\"(row.rsmnLink)\"]")
                ))
            except TimeoutException:
                print(f"→ No pending‐documents table for RUT {rut_value}, skipping.")
                return

            self._scrape_pending(
                wait,
                    "//a[@ui-sref and contains(normalize-space(.), 'Factura Electrónica')]",
                status="pending",
                doc_type="invoice",
                rut_value=rut_value,
                all_rows=all_rows,
            )

            self._scrape_pending(
                wait,
                "//a[@ui-sref and contains(normalize-space(.), 'Factura no Afecta o Exenta Electrónica')]",
                status="pending_exempt",
                doc_type="invoice",
                rut_value=rut_value,
                all_rows=all_rows,
            )

            self._scrape_pending(
                wait,
                "//a[@ui-sref and contains(normalize-space(.), 'Nota de Crédito Electrónica')]",
                status="pending",
                doc_type="credit_note",
                rut_value=rut_value,
                all_rows=all_rows,
            )

            if all_rows:
                df = pd.DataFrame(all_rows, columns=headers, dtype=str)
                # print(df.head())
                return df
        finally:
            self.driver.quit()