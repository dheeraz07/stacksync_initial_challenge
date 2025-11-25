import os
import json
import subprocess
import ast
import tempfile
import sys
import traceback
from flask import Flask, request, jsonify

app = Flask(__name__)

WRAPPER_TEMPLATE = """
import sys
import io
import json
import traceback

# Capture stdout
original_stdout = sys.stdout
sys.stdout = io.StringIO()

try:
    # Execute user code
    # We use a distinct global dictionary to avoid polluting the namespace too much,
    # but we need to execute in a way that 'main' becomes available.
    user_globals = {{}}
    exec(compile({user_script!r}, 'user_script.py', 'exec'), user_globals)

    # Check if main exists
    if 'main' not in user_globals or not callable(user_globals['main']):
        raise ValueError("Function 'main()' not found in script")

    # Run main
    result = user_globals['main']()

    # Serialize result
    try:
        # Ensure the result is JSON serializable
        # We serialize and deserialize to verify, or just dump it in the final output
        json.dumps(result)
    except (TypeError, ValueError):
        raise ValueError("Return value of main() is not JSON serializable")

    # Get captured stdout
    captured_stdout = sys.stdout.getvalue()

    # Prepare final output
    output = {{
        "result": result,
        "stdout": captured_stdout
    }}
    
    # Write to original stdout as the only output
    sys.stdout = original_stdout
    print(json.dumps(output))

except Exception:
    sys.stdout = original_stdout
    # We print the error to stderr so the parent process can catch it distinct from JSON output
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
"""

def validate_script(script_content):
    """Validate that the script is syntactically correct and defines main()."""
    try:
        tree = ast.parse(script_content)
    except SyntaxError:
        return False, "Syntax Error in script"

    has_main = any(isinstance(node, ast.FunctionDef) and node.name == "main" for node in tree.body)
    if not has_main:
        return False, "Script must contain a 'main()' function"
    return True, None

@app.route("/", methods=["GET"])
def health_check():
    """Simple health endpoint to verify the service is running."""
    return jsonify({"status": "active", "service": "Secure Python Executor", "version": "1.0"})

@app.route("/execute", methods=["POST"])
def execute_script():
    """Execute the provided user script inside an nsjail sandbox."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    if "script" not in data:
        return jsonify({"error": "Missing 'script' field"}), 400

    user_script = data["script"]

    # Basic validation of script
    is_valid, error_msg = validate_script(user_script)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    # Prepare wrapped script
    wrapped_script = WRAPPER_TEMPLATE.format(user_script=user_script)

    # Write to /tmp so nsjail can execute it with rw access
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py", dir="/tmp") as temp_script:
        temp_script.write(wrapped_script)
        temp_script_path = temp_script.name

    python_executable = sys.executable
    nsjail_cmd = [
        "nsjail",
        "--config",
        os.path.abspath("nsjail.cfg"),
        "--",
        python_executable,
        temp_script_path,
    ]

    try:
        process = subprocess.run(
            nsjail_cmd,
            capture_output=True,
            text=True,
            timeout=12,
        )
    finally:
        if os.path.exists(temp_script_path):
            os.unlink(temp_script_path)

    if process.returncode != 0:
        error_message = process.stderr.strip() if process.stderr else "Execution failed"

        # Detect nsjail timeouts explicitly
        if "run time >= time limit" in error_message:
            return jsonify({"error": "Execution timed out"}), 408

        return jsonify({"error": "Script execution failed", "stderr": error_message}), 400

    # Process succeeded: parse wrapper JSON
    try:
        output_json = json.loads(process.stdout.strip())
        return jsonify(output_json)
    except json.JSONDecodeError:
        return (
            jsonify(
                {
                    "error": "Invalid JSON output from script",
                    "raw_stdout": process.stdout,
                    "stderr": process.stderr,
                }
            ),
            500,
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
