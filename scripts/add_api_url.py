import yaml
import sys

def add_api_url(yaml_file, api_link):
    with open(yaml_file, 'r+') as f:
        data = yaml.safe_load(f)
        data['x-google-backend'] = {'address': api_link}
    with open(yaml_file, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

if __name__ == '__main__':
    yaml_file = sys.argv[1]
    api_link = sys.argv[2]
    add_api_url(yaml_file, api_link)