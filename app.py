from flask import Flask, request, render_template, send_file, flash, redirect
import pandas as pd
import os
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)
app.secret_key = "super_secret_key"

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            master_file = request.files.get("master_file")
            data_files = request.files.getlist("data_files")
            
            if not master_file or master_file.filename == "":
                flash("Please upload the Master File.")
                return redirect(request.url)
                
            if not data_files or data_files[0].filename == "":
                flash("Please upload at least one Data File.")
                return redirect(request.url)

            temp_dir = tempfile.mkdtemp()
            
            # 1. Save and read the Master File
            master_filename = secure_filename(master_file.filename)
            if not master_filename:
                master_filename = "MasterFile.xlsx"
            master_filepath = os.path.join(temp_dir, master_filename)
            master_file.save(master_filepath)
            
            # Read the master file to get the exact columns from the headers
            master_df = pd.read_excel(master_filepath)
            master_df.columns = master_df.columns.str.strip()
            target_columns = list(master_df.columns)
            
            if not target_columns:
                flash("The Master File is empty or has no columns!")
                return redirect(request.url)

            # 2. Process all Data Files
            df_list = [master_df] # We start with the master df so we keep its structure and any existing data
            
            target_columns_lower = [c.lower() for c in target_columns]
            
            for file in data_files:
                filename_lower = file.filename.lower() if file and file.filename else ""
                
                if filename_lower.endswith(('.xls', '.xlsx', '.xlsm', '.csv')):
                    filename = secure_filename(file.filename)
                    if not filename:
                        filename = f"data_file_{len(df_list)}.xlsx"
                    filepath = os.path.join(temp_dir, filename)
                    file.save(filepath)
                    
                    try:
                        # MEMORY FIX: Read only headers first (CSV or Excel)
                        if filename_lower.endswith('.csv'):
                            df_headers = pd.read_csv(filepath, nrows=0)
                        else:
                            df_headers = pd.read_excel(filepath, nrows=0)
                            
                        original_cols = list(df_headers.columns)
                        
                        # Create a mapping from original column name to the Master File's exact column name
                        use_cols_indices = []
                        col_rename_map = {}
                        
                        for i, col in enumerate(original_cols):
                            clean_col_lower = str(col).strip().lower()
                            if clean_col_lower in target_columns_lower:
                                use_cols_indices.append(i)
                                # Find the exact Master File name to use
                                master_exact_name = target_columns[target_columns_lower.index(clean_col_lower)]
                                col_rename_map[col] = master_exact_name
                        
                        if use_cols_indices:
                            # Load ONLY the needed columns into memory
                            if filename_lower.endswith('.csv'):
                                df = pd.read_csv(filepath, usecols=use_cols_indices)
                            else:
                                df = pd.read_excel(filepath, usecols=use_cols_indices)
                            
                            # Rename columns so they EXACTLY match the Master File (fixes dropped data)
                            df.rename(columns=col_rename_map, inplace=True)
                            
                            df_list.append(df.copy())
                        else:
                            flash(f"⚠️ Warning: Skipped '{file.filename}' because ZERO columns matched your Master File. Check spelling or ensure headers are in the very first row!")
                        
                        # Delete the file immediately after reading to free up space
                        os.remove(filepath)
                    except Exception as e:
                        flash(f"⚠️ Error reading '{file.filename}': {str(e)}")
                else:
                    if file and file.filename:
                        flash(f"⚠️ Warning: Skipped '{file.filename}' because it is an unsupported file type! Only .xls, .xlsx, and .csv are supported.")
                        
            # 3. Combine all data and return the updated Master File
            if len(df_list) > 1:
                # Combine all data, aligning it to the Master File's columns
                final_df = pd.concat(df_list, ignore_index=True)
                
                # Ensure the output has EXACTLY the same columns as the original master file in the same order
                final_df = final_df.reindex(columns=target_columns)
                
                # Auto-increment serial numbers across all files if a serial number column exists
                sr_col_variations = ['sr no', 'sr. no.', 's.no', 's.no.', 's no', 'sl no', 'sn', 'sr.no', 'sr.no.']
                for col in final_df.columns:
                    if str(col).strip().lower() in sr_col_variations:
                        # Replace the entire column with a continuous sequence from 1 to N
                        final_df[col] = list(range(1, len(final_df) + 1))
                        break
                
                # Save it back to a new file
                output_path = os.path.join(temp_dir, "Updated_" + master_filename)
                final_df.to_excel(output_path, index=False)
                
                return send_file(output_path, as_attachment=True, download_name="Updated_" + master_filename)
            else:
                flash("No matching data was found in any of the uploaded data files to add to the Master File.")
                return redirect(request.url)
                
        except Exception as e:
            flash(f"SYSTEM CRASH: {str(e)}")
            return redirect(request.url)
            
    return render_template("index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
