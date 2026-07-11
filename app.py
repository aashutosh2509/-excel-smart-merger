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
        master_filepath = os.path.join(temp_dir, master_filename)
        master_file.save(master_filepath)
        
        try:
            # Read the master file to get the exact columns from the headers
            master_df = pd.read_excel(master_filepath)
            master_df.columns = master_df.columns.str.strip()
            target_columns = list(master_df.columns)
            
            if not target_columns:
                flash("The Master File is empty or has no columns!")
                return redirect(request.url)
                
        except Exception as e:
            flash(f"Error reading Master File: {e}")
            return redirect(request.url)

        # 2. Process all Data Files
        df_list = [master_df] # We start with the master df so we keep its structure and any existing data
        
        for file in data_files:
            if file and file.filename.endswith(('.xls', '.xlsx')):
                filename = secure_filename(file.filename)
                filepath = os.path.join(temp_dir, filename)
                file.save(filepath)
                
                try:
                    df = pd.read_excel(filepath)
                    df.columns = df.columns.str.strip()
                    
                    # Keep only columns that exist in BOTH the data file and the master file
                    available_cols = [col for col in target_columns if col in df.columns]
                    
                    if available_cols:
                        df_filtered = df[available_cols].copy()
                        df_list.append(df_filtered)
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
                    
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
            
    return render_template("index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
