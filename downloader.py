from utils import save_maps
from rpc import send_command

def map_assets():
    assets = send_command('listassets', ["", True])

    by_name = {}
    by_height = {}  # {<height>: {<name>: <data>}}
    by_blockhash = {}
    by_ipfshash = {}
    by_amount = {}  # {<qty>: {<name>: <data>}}
    by_units = {}  # {<qty>: {<name>: <data>}}
    by_reissuable = {}  # {<reissuable>: {<name>: <data>}}

    # Map all the assets for quick retrieval
    for asset_name in assets:

        # Get the asset data
        asset_data = assets[asset_name]

        # Map the asset by name (this is super easy)
        by_name[asset_name] = asset_data

        # Map the asset by block height 
        try:
            by_height[int(asset_data['block_height'])][asset_name] = asset_data
        except KeyError:
            by_height[int(asset_data['block_height'])] = {}
            by_height[int(asset_data['block_height'])][asset_name] = asset_data

        # Map by block hash
        try:
            by_blockhash[asset_data['blockhash']][asset_name] = asset_data
        except KeyError:
            by_blockhash[asset_data['blockhash']] = {}
            by_blockhash[asset_data['blockhash']][asset_name] = asset_data

        # Map by ipfs hash (If there is one)
        if asset_data['has_ipfs'] == 1:
            try:
                by_ipfshash[asset_data['ipfs_hash']] = asset_data
            except:
                pass
                
        # Map by amount (These are aggregated)
        try:
            by_amount[int(asset_data['amount'])][asset_name] = asset_data
        except KeyError:
            by_amount[int(asset_data['amount'])] = {}
            by_amount[int(asset_data['amount'])][asset_name] = asset_data

        # Map by units (Also aggregated)
        try:
            by_units[int(asset_data['units'])][asset_name] = asset_data
        except KeyError:
            by_units[int(asset_data['units'])] = {}
            by_units[int(asset_data['units'])][asset_name] = asset_data

        # Map by reissuable (Super aggregated)
        try:
            by_reissuable[asset_data['reissuable']][asset_name] = asset_data
        except KeyError:
            by_reissuable[asset_data['reissuable']] = {}
            by_reissuable[asset_data['reissuable']][asset_name] = asset_data

    # Sort the maps by their keys
    sorted_by_name = {k: by_name[k] for k in sorted(by_name)}
    sorted_by_height = {k: {sk: by_height[k][sk] for sk in sorted(by_height[k])} for k in sorted(by_height)}
    sorted_by_blockhash = {k: {sk: by_blockhash[k][sk] for sk in sorted(by_blockhash[k])} for k in sorted(by_blockhash)}
    sorted_by_ipfshash = {k: by_ipfshash[k] for k in sorted(by_ipfshash)}
    sorted_by_amount = {k: {sk: by_amount[k][sk] for sk in sorted(by_amount[k])} for k in sorted(by_amount)}
    sorted_by_units = {k: {sk: by_units[k][sk] for sk in sorted(by_units[k])} for k in sorted(by_units)}
    sorted_by_reissuable = {k: {sk: by_reissuable[k][sk] for sk in sorted(by_reissuable[k])} for k in sorted(by_reissuable)}

    # List of maps to save with their corresponding file paths
    maps_to_save = [
        (sorted_by_name, './data/maps/by_name.json'),
        (sorted_by_height, './data/maps/by_height.json'),
        (sorted_by_blockhash, './data/maps/by_blockhash.json'),
        (sorted_by_ipfshash, './data/maps/by_ipfshash.json'),
        (sorted_by_amount, './data/maps/by_amount.json'),
        (sorted_by_units, './data/maps/by_units.json'),
        (sorted_by_reissuable, './data/maps/by_reissuable.json'),
    ]
    
    save_maps(maps_to_save)

    return (
        sorted_by_name,
        sorted_by_height,
        sorted_by_blockhash,
        sorted_by_ipfshash,
        sorted_by_amount,
        sorted_by_units,
        sorted_by_reissuable
    )
