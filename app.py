import os
import pandas as pd
from flask import Flask, request, render_template, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Path to the default master CSV file
master_csv_path = "Salary_Slip_Master_Data.xlsx"
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure upload folder exists

# Global variable to store data
data_frame = None

@app.route("/", methods=["GET", "POST"])
def index():
    global data_frame  # Use the global data_frame variable

    if request.method == "POST":
        emp_code = request.form["emp_code"]
        month = request.form["month"]
        file = request.files.get("file")

        # If a file is uploaded
        if file and file.filename:
            # Save the uploaded file to persist as master
            global master_csv_path  # Update the global master file path
            master_csv_path = os.path.join(UPLOAD_FOLDER, "Salary_Slip_Master_Data.xlsx")
            file.save(master_csv_path)  # Save file permanently in the uploads directory
            print(f"Uploaded file is now set as the master file: {master_csv_path}")  # Debug

            # Load the data into the global data_frame
            data_frame = load_data(master_csv_path)

        # Ensure the master file exists
        if data_frame is None:
            return "The file 'Salary_Slip_Master_Data.xlsx' could not be found. Please ensure the file exists or upload it."

        # Validate employee code and month
        validation_error = validate_input(emp_code, month, data_frame)
        if validation_error:
            return validation_error  # Show validation error to the user

        # Generate salary slip if validation succeeds
        salary_slip = generate_salary_slip(emp_code, month, data_frame, UPLOAD_FOLDER)
        if salary_slip:
            return send_file(salary_slip, as_attachment=True)
        else:
            return (
                "Employee data for the specified Employee Code and Month not found.",
                404,
            )

    return render_template("index.html")

def load_data(file_path):
    """
    Loads data from the given file path into a DataFrame.
    """
    try:
        _, file_extension = os.path.splitext(file_path)
        if file_extension == ".csv":
            return pd.read_csv(file_path)
        elif file_extension in [".xls", ".xlsx"]:
            return pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file format. Please upload a valid CSV or Excel file.")
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

def validate_input(emp_code, month, df):
    """
    Validates whether the given Employee Code and Salary Month exist in the data.
    """
    try:
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
        print("Unique Employee Codes:", df["emp code"].astype(str).unique())  # Debug
        if emp_code not in df["emp code"].astype(str).unique():
            return f"Employee Code '{emp_code}' not found in the file."

        # Validate Salary Month exists
        print("Unique Months:", df["month"].astype(str).unique())  # Debug
        if month not in df["month"].astype(str).unique():
            return f"Salary Month '{month}' is invalid or not found in the file."

    except Exception as e:
        print(f"Error validating input: {e}")
        return "An error occurred while processing the file. Please check its format."

    # If validations pass, return None
    return None

def generate_salary_slip(emp_code, month, df, upload_folder):
    try:
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

        # ------- Employee Details -------
        # Ensure all required details populate correctly
        employee_details_columns = [
            "month", "emp code", "employee name", "department", "location",
            "uan no", "doj", "grade", "section", "standard days", "paid days",
            "lwp", "pan no", "adhaar no", "account no.", "ifsc code", "paymode"
        ]
        # Normalize keys for the template and extract column values
        employee_details = {
            col.replace(" ", "_").capitalize(): emp_data.get(col, "-").split()[0] if col == "doj" else emp_data.get(col, "-")
            for col in employee_details_columns
        }

        # ------- Earnings -------
        earning_columns = [
            "basic", "hra", "other allowance", "attendance incentive",
            "medical allowance", "washing allowance", "conveyance allowance",
            "stipend", "incentive", "re-location allowance/joining exp/medical checkup",
            "other earnings"
        ]
        earnings = {col.capitalize(): int(float(emp_data.get(col, 0))) for col in earning_columns}  # Convert to integer
        gross_pay = sum(earnings.values())  # Sum up all earnings

        # ------- Deductions -------
        deduction_columns = [
            "cmpf", "family pension fund", "epf", "recovery"
        ]
        deductions = {col.capitalize(): int(float(emp_data.get(col, 0))) for col in
                      deduction_columns}  # Convert to integer
        total_deductions = sum(deductions.values())  # Sum up all deductions

        # ------- Net Pay Calculation -------
        net_pay = gross_pay - total_deductions
        net_pay_text_1 = "Net Pay = Gross Pay - Total Deductions"
        net_pay_text_2 = f"{gross_pay} - {total_deductions} = {net_pay}"
        net_pay_text_3 = f"{net_pay}"

        # ------- Split Employee Details for Two-Column Layout -------
        emp_details_items = list(employee_details.items())
        emp_details_left = dict(emp_details_items[:len(emp_details_items) // 2])  # First half of the items
        emp_details_right = dict(emp_details_items[len(emp_details_items) // 2:])  # Second half of the items

        # ------- Split Earnings for Two-Column Layout -------
        earnings_items = list(earnings.items())
        earnings_left = dict(earnings_items[:len(earnings_items) // 2])  # First half of the items
        earnings_right = dict(earnings_items[len(earnings_items) // 2:])  # Second half of the items

        # ------- Generate HTML using Jinja template -------
        html_content = render_template(
            "salary_slip.html",
            emp_details_left=emp_details_left,  # Left column of employee details
            emp_details_right=emp_details_right,  # Right column of employee details
            earnings_left=earnings_left,  # Left column of earnings
            earnings_right=earnings_right,  # Right column of earnings
            deductions=deductions,  # Deductions data
            gross=gross_pay,  # Gross pay
            net_pay_text_1=net_pay_text_1,
            net_pay_text_2=net_pay_text_2,
            net_pay_text_3=net_pay_text_3,
            net_pay=net_pay
        )

        # Save HTML file
        output_filename = f"salary_slip_{emp_code}_{month}.html"
        output_path = os.path.join(upload_folder, output_filename)

        with open(output_path, "w") as html_file:
            html_file.write(html_content)

        return output_path

    except Exception as e:
        # Graceful error handling with error logging
        print(f"Error generating salary slip: {e}")
        return None

if __name__ == "__main__":
    app.run(debug=True)
