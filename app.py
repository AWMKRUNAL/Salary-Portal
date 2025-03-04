import os
import pandas as pd
from flask import Flask, request, render_template, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)


# Default path to the master file
DEFAULT_MASTER_FILE = "Salary_Slip_Master_Data.xlsx"
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
CONFIG_FILE = os.path.join(app.root_path, "config.txt")  # Path to store persisted file path

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_master_file_path():
    """
    Reads the persisted master file path from the config file.
    If the config file doesn't exist, default to DEFAULT_MASTER_FILE.
    """
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            path = f.read().strip()
            if os.path.exists(path):  # Ensure the file still exists
                return path
    # Default to the predefined master file path
    return os.path.join(UPLOAD_FOLDER, DEFAULT_MASTER_FILE)


def save_master_file_path(path):
    """
    Saves the given master file path to the config file for persistence.
    """
    with open(CONFIG_FILE, "w") as f:
        f.write(path)


# Initialize the master CSV path
master_csv_path = get_master_file_path()


@app.route("/", methods=["GET", "POST"])
def index():
    global master_csv_path  # Access the global master file path variable
    if request.method == "POST":
        emp_code = request.form["emp_code"]
        month = request.form["month"]
        file = request.files.get("file")

        # If a file is uploaded
        if file and file.filename:
            # Save the uploaded file to persist as the master file
            master_csv_path = os.path.join(UPLOAD_FOLDER, secure_filename("Salary_Slip_Master_Data.xlsx"))
            file.save(master_csv_path)  # Save file permanently in the uploads directory
            save_master_file_path(master_csv_path)  # Persist this path to the config file
            print(f"Uploaded file is now set as the master file: {master_csv_path}")  # Debug

        # Ensure the master file exists
        if not os.path.exists(master_csv_path):
            return "The file 'Salary_Slip_Master_Data.xlsx' could not be found. Please ensure the file exists or upload it."

        # Validate employee code and month
        validation_error = validate_input(emp_code, month, master_csv_path)
        if validation_error:
            return validation_error  # Show validation error to the user

        # Generate salary slip if validation succeeds
        salary_slip = generate_salary_slip(emp_code, month, master_csv_path, UPLOAD_FOLDER)
        if salary_slip:
            return send_file(salary_slip, as_attachment=True)
        else:
            return (
                "Employee data for the specified Employee Code and Month not found.",
                404,
            )

    return render_template("index.html")


def validate_input(emp_code, month, file_path):
    """
    Validates whether the given Employee Code and Salary Month exist in the data.
    """
    try:
        # Detect file extension to determine how to read the file
        _, file_extension = os.path.splitext(file_path)

        # Load the file based on its type
        if file_extension == ".csv":
            df = pd.read_csv(file_path)
        elif file_extension in [".xls", ".xlsx"]:
            df = pd.read_excel(file_path)
        else:
            return "Unsupported file format. Please upload a valid CSV or Excel file."

        # Normalize column names: strip whitespace and convert to lowercase
        df.columns = df.columns.str.strip().str.lower()
        print("Columns in the file (after normalization):", df.columns.tolist())  # Debug

        # Required column names in lowercase (normalize for validation)
        required_columns = ["emp code", "month"]  # Already lowercase
        for col in required_columns:
            if col not in df.columns:
                print(f"Missing column: {col}. Available columns: {df.columns.tolist()}")  # Debug
                return f"The file is missing the required column: '{col}'."

        # Validate Employee Code exists
        emp_code = str(emp_code)  # Ensure emp_code is treated as a string
        if emp_code not in df["emp code"].astype(str).unique():
            return f"Employee Code '{emp_code}' not found in the file."

        # Validate Salary Month exists
        if month not in df["month"].astype(str).unique():
            return f"Salary Month '{month}' is invalid or not found in the file."

    except FileNotFoundError:
        return f"The file '{file_path}' could not be found. Please ensure the file exists."
    except Exception as e:
        print(f"Error validating input: {e}")
        return "An error occurred while processing the file. Please check its format."

    # If validations pass, return None
    return None


def generate_salary_slip(emp_code, month, file_path, upload_folder):
    try:
        # Detect file extension to determine how to read the file
        _, file_extension = os.path.splitext(file_path)

        if file_extension == ".csv":
            df = pd.read_csv(file_path)
        elif file_extension in [".xls", ".xlsx"]:
            df = pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file format. Must be .csv, .xls, or .xlsx.")

        # Normalize column names to lowercase
        df.columns = df.columns.str.strip().str.lower()

        # Filter for the provided Employee Code and Month
        emp_data = df[
            (df["emp code"].astype(str) == str(emp_code))
            & (df["month"].astype(str) == str(month))
            ]
        if emp_data.empty:
            raise ValueError(f"No records found for Employee Code {emp_code} and Month {month}.")

        # Extract data for the slip (use only the first matching record if multiple exist)
        emp_data = emp_data.iloc[0]

        # ------- Map for Display Fields -------
        FIELD_DISPLAY_NAMES = {
            "emp code": "Employee Code",
            "employee name": "Employee Name",
            "uan no": "UAN",
            "doj": "DOJ",
            "standard days": "Standard Days",
            "paid days": "Paid Days",
            "lwp": "LWP",
            "pan no": "PAN",
            "adhaar no": "Aadhaar Number",
            "ifsc code": "IFSC Code",
            "hra": "HRA",
            "cmpf": "CMPF",
            "family pension fund": "Family Pension Fund",
            "epf": "EPF",
            "account no.": "Account Number",
            "sick leave" : "Sick Leave",
            "casual leave": "Casual Leave",
            "privilege leave": "Privilege Leave"
        }

        # ------- Employee Details -------
        employee_details_columns = [
            "month", "emp code", "employee name", "department", "location",
            "uan no", "doj", "grade", "section", "standard days", "paid days",
            "lwp", "pan no", "adhaar no", "account no.", "ifsc code", "paymode"
        ]
        # Format employee details with display names and adjusted values
        employee_details = {
            FIELD_DISPLAY_NAMES.get(col.lower(), col.replace(" ", "_").capitalize()): (
                str(emp_data.get(col, "")).split(" ")[0]  # Format date fields
                if col.lower() in ["doj"] else emp_data.get(col, "-")
            )
            for col in employee_details_columns
        }

        # ------- Earnings -------
        earning_columns = [
            "basic", "hra", "other allowance", "attendance incentive",
            "medical allowance", "washing allowance", "conveyance allowance",
            "stipend", "incentive", "re-location allowance/joining exp/medical checkup",
            "other earnings"
        ]
        earnings = {
            FIELD_DISPLAY_NAMES.get(col.lower(), col.capitalize()): int(float(emp_data.get(col, 0)))
            for col in earning_columns
        }
        gross_pay = sum(earnings.values())  # Calculate gross pay

        # ------- Deductions -------
        deduction_columns = ["cmpf", "family pension fund", "epf", "recovery"]
        deductions = {
            FIELD_DISPLAY_NAMES.get(col.lower(), col.capitalize()): int(float(emp_data.get(col, 0)))
            for col in deduction_columns
        }
        total_deductions = sum(deductions.values())  # Calculate total deductions

        # ------- Net Pay Calculation -------
        net_pay = gross_pay - total_deductions
        net_pay_text_1 = "Net Pay = Gross Pay - Total Deductions"
        net_pay_text_2 = f"{gross_pay} - {total_deductions} = {net_pay}"
        net_pay_text_3 = f"{net_pay}"

        # ------- Leave Balance -------
        leave_balance_columns = ["sick leave", "casual leave", "privilege leave"]
        leave_balance = {
            FIELD_DISPLAY_NAMES.get(col.lower(), col.capitalize()): int(float(emp_data.get(col, 0)))
            for col in leave_balance_columns
        }
        leave_balance_total = sum(leave_balance.values())  # Total leave balance

        # ------- Generate HTML using Jinja template -------
        html_content = render_template(
            "salary_slip.html",
            emp_details=employee_details,
            earnings=earnings,
            deductions=deductions,
            gross=gross_pay,
            net_pay_text_1=net_pay_text_1,
            net_pay_text_2=net_pay_text_2,
            net_pay_text_3=net_pay_text_3,
            net_pay=net_pay,
            leave_balance = leave_balance,
            leave_balance_total=leave_balance_total
            
        )

        # Save HTML file
        output_filename = f"salary_slip_{emp_code}_{month}.html"
        output_path = os.path.join(upload_folder, output_filename)

        with open(output_path, "w") as html_file:
            html_file.write(html_content)

        return output_path

    except Exception as e:
        print(f"Error generating salary slip: {e}")
        return None


if __name__ == "__main__":
    app.run(debug=True)
