import frappe
import json
import requests
import pyqrcode

def sign_einvoice(doc, method):

    if doc.company_tax_id is None:
        frappe.throw("Company Tax ID/PIN required")
    # if doc.tax_id is None:
    #     frappe.throw("Customer Tax ID/PIN Required")

    base_grand_total = doc.base_grand_total * -1 if doc.is_return == 1 else doc.base_grand_total
    base_net_total = doc.base_net_total * -1 if doc.is_return == 1 else doc.base_net_total
    base_total_taxes_and_charges = doc.base_total_taxes_and_charges * -1 if doc.is_return == 1 else doc.base_total_taxes_and_charges
    rel_doc_number = ""

    if doc.return_against:
        rel_doc_number = frappe.db.get_value("Sales Invoice", doc.return_against, "custom_cu_invoice_number")

    if doc.custom_return_against_previous_year:
        rel_doc_number = doc.custom_return_against_previous_year


    req = {
        "invoice_date": frappe.utils.format_date(str(doc.posting_date),"dd_MM_Y"), # "25_02_2022"
        "invoice_number": doc.name, # "250220221134"
        "invoice_pin": doc.company_tax_id,
        "customer_pin": doc.tax_id or "",
        "customer_exid": "",
        "grand_total": frappe.utils.fmt_money(base_grand_total).replace(',', ''),
        "net_subtotal": frappe.utils.fmt_money(base_net_total).replace(',', ''),
        "tax_total": frappe.utils.fmt_money(base_total_taxes_and_charges).replace(',', ''),
        "net_discount_total": "0",
        "sel_currency": "KSH",
        "rel_doc_number": rel_doc_number,
        "items_list": []
    }

    for item in doc.items:
        qty = item.qty * -1 if doc.is_return == 1 else item.qty
        amount = item.amount * -1 if doc.is_return == 1 else item.amount
        item = f"{item.custom_hs_code or ""} {trim(item.item_name) } { frappe.utils.fmt_money(qty).replace(',', '') } { frappe.utils.fmt_money(item.rate).replace(',', '') } { frappe.utils.fmt_money(amount).replace(',', '') }"
        req["items_list"].append(item)

    host = frappe.db.get_value("Branch", doc.branch, "custom_einvoice_host")
    auth_key = frappe.db.get_value("Branch", doc.branch, "custom_einvoice_auth_key")

    url = f"{host}/api/sign?invoice+1"

    if doc.is_return == 1:
        url = f"{host}/api/sign?credit-note+1"

    if doc.is_debit_note == 1:
        url = f"{host}/api/sign?debit-note+1"

    headers = {
        'Content-Type': 'application/json',
        'Authorization': auth_key
    }

    frappe.log_error("einvoic_req", req)

    try:
        response = requests.post(url, headers=headers, data=json.dumps(req))

        frappe.log_error('einvoice log', response.text)
        fixed_content = response.text.replace("\\:", ":").replace("\\/", "/")
        fixed_json = json.loads(fixed_content)
        frappe.log_error('einvoice log_json', fixed_json.get("cu_serial_number"))
        
        if fixed_json.get("error_status"):
            frappe.throw(f"E Invoice Error : {fixed_json.get('error_status')}")

        frappe.db.set_value("Sales Invoice", doc.name, "custom_cu_serial_number", fixed_json.get("cu_serial_number"))
        frappe.db.set_value("Sales Invoice", doc.name, "custom_cu_invoice_number", fixed_json.get("cu_invoice_number"))
        frappe.db.set_value("Sales Invoice", doc.name, "custom_original_cu_invoice_number", rel_doc_number)
        frappe.db.set_value("Sales Invoice", doc.name, "custom_verify_url", fixed_json.get("verify_url"))
        frappe.db.set_value("Sales Invoice", doc.name, "custom_description", fixed_json.get("description"))

        frappe.msgprint("EInvoice Generated Successfully")

    except Exception as e:
        frappe.log_error(e)
        frappe.throw("EInvoie Error")
    
    
def trim(string):

    unwanted_patterns = ['</div>', '&', '"', "'", '>', '<', ' ', '(', ')', '/']
    
    for pattern in unwanted_patterns:
        string = string.replace(pattern, '')
    
    return string


def get_qr_code(value, scale):
    qr = pyqrcode.create(value).png_as_base64_str(scale=scale, quiet_zone=1)
    return f'<img src="data:image/png;base64,{ qr }" class="qrcode">'


