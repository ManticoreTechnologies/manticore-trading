"""Script to generate HTML documentation for each API route."""

import os
import sys
import inspect
import json
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, Security
from fastapi.routing import APIWebSocketRoute
from pydantic import BaseModel

# Import all routers
from api.auth import router as auth_router
from api.listings import router as listings_router
from api.orders import router as orders_router
from api.market import router as market_router
from api.profile import router as profile_router
from api.chat import router as chat_router
from api.notifications import router as notifications_router
from api.system import router as system_router
from api.websockets import router as websocket_router

def get_model_schema(model: BaseModel) -> Dict[str, Any]:
    """Get JSON schema for a Pydantic model."""
    return model.schema()

def get_route_info(router: APIRouter) -> List[Dict[str, Any]]:
    """Extract route information from a FastAPI router."""
    routes = []
    for route in router.routes:
        # Get endpoint metadata
        endpoint = {
            'path': route.path,
            'name': route.name,
            'description': inspect.cleandoc(route.endpoint.__doc__ or ''),
            'requires_auth': False,
            'parameters': [],
            'request_body': None,
            'responses': {},
            'is_websocket': isinstance(route, APIWebSocketRoute)
        }

        # Add methods for HTTP routes
        if not endpoint['is_websocket']:
            endpoint['methods'] = route.methods

        # Check for authentication requirement
        for dependency in route.dependencies:
            if isinstance(dependency.dependency, (Depends, Security)):
                if 'get_current_user' in str(dependency.dependency.dependency):
                    endpoint['requires_auth'] = True

        # Get function signature
        sig = inspect.signature(route.endpoint)
        
        # Get parameters
        for name, param in sig.parameters.items():
            if name not in ['request', 'background_tasks', 'websocket']:
                param_info = {
                    'name': name,
                    'type': str(param.annotation),
                    'required': param.default == param.empty,
                    'default': None if param.default == param.empty else param.default
                }
                
                # If parameter is a Pydantic model, get its schema
                if hasattr(param.annotation, '__pydantic_model__'):
                    param_info['schema'] = get_model_schema(param.annotation)
                
                endpoint['parameters'].append(param_info)

        # Get request body if any
        for param in sig.parameters.values():
            if hasattr(param.annotation, '__pydantic_model__'):
                endpoint['request_body'] = {
                    'model': param.annotation.__name__,
                    'schema': get_model_schema(param.annotation)
                }

        routes.append(endpoint)
    
    return routes

def generate_html(router: APIRouter, name: str) -> str:
    """Generate HTML documentation for a router."""
    routes = get_route_info(router)
    
    # Start with the template
    template_path = Path(__file__).parent / 'template.html'
    with open(template_path, 'r') as f:
        template = f.read()
    
    # Generate content for each route
    content = f'<h1>{name} API</h1>\n'
    content += f'<p class="lead">{inspect.cleandoc(router.__doc__ or "")}</p>\n\n'
    
    # Add search and filters
    content += '''
    <div class="controls mb-4">
        <input type="text" id="endpoint-search" class="form-control mb-2" placeholder="Search endpoints...">
        <div class="btn-group">
            <button class="btn btn-outline-primary method-filter active" data-method="all">All</button>
            <button class="btn btn-outline-primary method-filter" data-method="get">GET</button>
            <button class="btn btn-outline-primary method-filter" data-method="post">POST</button>
            <button class="btn btn-outline-primary method-filter" data-method="put">PUT</button>
            <button class="btn btn-outline-primary method-filter" data-method="delete">DELETE</button>
            <button class="btn btn-outline-primary method-filter" data-method="ws">WebSocket</button>
        </div>
    </div>
    '''
    
    # Generate endpoint documentation
    for route in routes:
        content += '<div class="endpoint">\n'
        
        # Header
        content += f'<h3>{route["name"]}</h3>\n'
        if route['is_websocket']:
            content += '<span class="method websocket">WebSocket</span>\n'
        else:
            for method in route['methods']:
                content += f'<span class="method {method.lower()}">{method}</span>\n'
        content += f'<span class="path">{route["path"]}</span>\n'
        
        # Description
        if route['description']:
            content += f'<p class="description">{route["description"]}</p>\n'
        
        # Authentication requirement
        if route['requires_auth']:
            content += '<p class="auth-required">Requires Authentication</p>\n'
        
        # Parameters
        if route['parameters']:
            content += '<h4>Parameters</h4>\n'
            content += '<div class="params">\n'
            content += '<table class="table">\n'
            content += '<thead><tr><th>Name</th><th>Type</th><th>Required</th><th>Description</th></tr></thead>\n'
            content += '<tbody>\n'
            for param in route['parameters']:
                content += f'''<tr>
                    <td>{param["name"]}</td>
                    <td><code>{param["type"]}</code></td>
                    <td>{"<span class='required'>Yes</span>" if param["required"] else "<span class='optional'>No</span>"}</td>
                    <td>{param.get("description", "")}</td>
                </tr>\n'''
            content += '</tbody></table></div>\n'
        
        # Request body
        if route['request_body']:
            content += '<h4>Request Body</h4>\n'
            content += '<pre><code class="language-json">'
            content += json.dumps(route['request_body']['schema'], indent=2)
            content += '</code></pre>\n'
        
        # Example request
        content += '<h4>Example Request</h4>\n'
        content += '<div class="curl-example">\n'
        content += '<button class="copy-btn">Copy</button>\n'
        content += '<pre><code class="language-bash">'
        
        # Generate example based on type
        if route['is_websocket']:
            content += f'''// JavaScript WebSocket example
const ws = new WebSocket('ws://localhost:8000{route["path"]}');

ws.onopen = () => {{
    console.log('Connected to WebSocket');
}};

ws.onmessage = (event) => {{
    const data = JSON.parse(event.data);
    console.log('Received:', data);
}};

ws.onerror = (error) => {{
    console.error('WebSocket error:', error);
}};

ws.onclose = () => {{
    console.log('WebSocket connection closed');
}};'''
        else:
            # Generate curl example for HTTP routes
            curl = f'curl -X {list(route["methods"])[0]} http://localhost:8000{route["path"]}'
            if route['requires_auth']:
                curl += ' \\\n    -H "Authorization: Bearer your-jwt-token"'
            if route['request_body']:
                curl += ' \\\n    -H "Content-Type: application/json"'
                curl += ' \\\n    -d \'{\n'
                # Add example values for each required field
                schema = route['request_body']['schema']
                required = schema.get('required', [])
                properties = schema.get('properties', {})
                example = {
                    k: "example_value" if properties[k]['type'] == 'string'
                    else 0 if properties[k]['type'] == 'integer'
                    else 0.0 if properties[k]['type'] == 'number'
                    else [] if properties[k]['type'] == 'array'
                    else {} if properties[k]['type'] == 'object'
                    else False
                    for k in required
                }
                curl += json.dumps(example, indent=8)
                curl += '\n    }\''
            content += curl
            
        content += '</code></pre>\n'
        content += '</div>\n'
        
        content += '</div>\n'
    
    # Replace template content
    html = template.replace('<!-- Content will be replaced for each route -->', content)
    
    return html

def main():
    """Generate documentation for all routes."""
    # Create docs directory if it doesn't exist
    docs_dir = Path(__file__).parent
    docs_dir.mkdir(exist_ok=True)
    
    # Generate documentation for each router
    routers = {
        'auth': auth_router,
        'listings': listings_router,
        'orders': orders_router,
        'market': market_router,
        'profile': profile_router,
        'chat': chat_router,
        'notifications': notifications_router,
        'system': system_router,
        'websockets': websocket_router
    }
    
    for name, router in routers.items():
        html = generate_html(router, name.title())
        with open(docs_dir / f'{name}.html', 'w') as f:
            f.write(html)
        print(f'Generated documentation for {name}')

if __name__ == '__main__':
    main() 