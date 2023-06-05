import re
from github import Github
import tkinter as tk
import yaml
from tkinter import messagebox, Label
from ttkthemes import ThemedTk
import re
from tkinter.ttk import Treeview
from xml.etree import ElementTree as ET
import time

# GitHub token (replace with your own token)
token = "GITHUB_TOKEN"


def find_args_in_launch_xml(file_content):
    root = ET.fromstring(file_content)
    args = root.findall('arg')

    matches = []
    for arg in args:
        name = arg.get('name')
        value = arg.get('value', '')
        default = arg.get('default', '')
        doc = arg.get('doc', '')

        matches.append((name, value, default, doc))

    return matches

def find_parameters_in_yaml(yaml_content):
    parameters = []

    def helper(yaml_content, prefix=''):
        if isinstance(yaml_content, dict):
            for key, value in yaml_content.items():
                new_prefix = f'{prefix}.{key}' if prefix else key
                if isinstance(value, dict):
                    helper(value, new_prefix)
                else:
                    parameters.append((new_prefix, str(value)))

    for key, value in yaml_content.items():
        if isinstance(value, dict) and 'ros__parameters' in value:
            helper(value['ros__parameters'], key)

    return parameters

def find_declare_launch_argument(file_content, file_type):
    if file_type == 'py':
        pattern = r'DeclareLaunchArgument\(([^,]*),([^,]*),?([^)]*)\)?'
        matches = re.findall(pattern, file_content)
        results = []

        for match in matches:
            name = match[0].strip()
            value = match[1].strip()
            description = match[2].strip() if len(match) > 2 else ''

            if value.startswith('default_value=os.path.join('):
                # extract the variable name used as prefix
                prefix_var_name = re.search(r'default_value=os.path.join\(([^,]*),', value)
                if prefix_var_name:
                    prefix_var_name = prefix_var_name.group(1).strip()

                    # find the definition of this variable in the file
                    prefix_value_pattern = fr'{prefix_var_name}\s*=\s*get_package_share_directory\(["\']([^"\']*)["\']\)'
                    prefix_value_matches = re.search(prefix_value_pattern, file_content)
                    prefix_value = prefix_value_matches.group(1) if prefix_value_matches else None

                    if prefix_value:
                        value = value.replace(f'os.path.join({prefix_var_name},', f'os.path.join(get_package_share_directory({prefix_value}),')
            if value.startswith('default_value='):
                value = value[len('default_value='):]
            if description.startswith('description='):
                description = description[len('description='):]
            results.append((name, value, description))
        return results
    elif file_type == 'yaml':
        yaml_content = yaml.safe_load(file_content)
        return find_parameters_in_yaml(yaml_content)
    else:
        return []

def search_repository():
    try:
        start_time = time.time()
        g = Github(token)
        repo_url = url_entry.get()
        user_name, repo_name = repo_url.split('/')[-2:]
        # Clear previous data
        for i in tree.get_children():
            tree.delete(i)
        status_label['text'] = "Scanning files..."
        # Create root nodes
        launch_root = tree.insert("", "end", text="LaunchFiles", open=True)
        param_root = tree.insert("", "end", text="ParameterFiles", open=True)
        scanned_files = 0
        repo = g.get_user(user_name).get_repo(repo_name)

        files = repo.get_contents("")
        

        while files:
            file_content = files.pop(0)
            if file_content.type == "dir":
                files.extend(repo.get_contents(file_content.path))
            else:
                matches = None
                if file_content.name.endswith('.launch.py') or file_content.name.endswith('_launch.py'):
                    content = file_content.decoded_content.decode('utf-8')
                    root_node = launch_root
                    matches = find_declare_launch_argument(content, 'py')
                elif file_content.name.endswith('.yaml'):
                    content = file_content.decoded_content.decode('utf-8')
                    root_node = param_root
                    matches = find_declare_launch_argument(content, 'yaml')
                elif file_content.name.endswith('.launch') or file_content.name.endswith('.launch.xml'):
                    xml_content = file_content.decoded_content.decode()
                    matches = find_args_in_launch_xml(xml_content)
                    root_node = launch_root

                if matches:  # only insert into tree if there are matches
                    file_item = tree.insert(root_node, "end", text=file_content.path, open=False)
                    for match in matches:
                        if len(match) == 4:
                            name, value, default, doc = match
                            arg_item = tree.insert(file_item, "end", text=name)
                            tree.insert(arg_item, "end", text=f'Value: {value}')
                            tree.insert(arg_item, "end", text=f'Default: {default}')
                            tree.insert(arg_item, "end", text=f'Description: {doc}')
                        elif len(match) == 3:
                            name, value, description = match
                            arg_item = tree.insert(file_item, "end", text=name)
                            tree.insert(arg_item, "end", text=f'Value: {value}')
                            tree.insert(arg_item, "end", text=f'Description: {description}')
                        else:
                            name, value = match
                            arg_item = tree.insert(file_item, "end", text=name)
                            tree.insert(arg_item, "end", text=f'Value: {value}')
                        
                scanned_files += 1
                status_label['text'] = f"Scanned {scanned_files} files..."
                status_label['background'] = 'blue'

                root.update()

    except Exception as e:
        messagebox.showerror("Error", e)
    elapsed_time = time.time() - start_time
    status_label['text'] = f"Scanning finished! (Time taken: {elapsed_time:.2f} seconds. Files scanned: {scanned_files})"

    status_label['background'] = 'green'
        
# GUI
root = ThemedTk(theme="arc")
root.title("GitHub Repo ROS Parser")
root.geometry("800x600")

# URL entry
url_entry = tk.Entry(root, width=100)
url_entry.pack(pady=10)
url_entry.insert(0, 'https://github.com/open-rmf/rmf_visualization')  # Replace with your repository URL

# token_entry = tk.Entry(root, width=100)
# token_entry.pack(pady=10)
# token_entry.insert(0, token)  # Replace with your repository URL

# Search button
search_button = tk.Button(root, text="Search", command=search_repository)
search_button.pack(pady=10)

# Treeview
tree = Treeview(root)
tree.pack(fill="both", expand=True)

# Status label
status_label = Label(root, text="Ready to scan!")
status_label.pack(pady=10)

root.mainloop()

