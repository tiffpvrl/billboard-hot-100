import requests
import time
import csv
import os
import re

API_TOKEN = 'xVyuevzgElHVficnEuoMABcLszGrnkJFsOhnnJCR'
headers = {
    'Authorization': f'Discogs token={API_TOKEN}',
    'User-Agent': 'YourAppName/1.0'
}

def clean_artist_name(artist_name):
    """
    Extract the main artist name by removing features and collaborators
    Handles formats like:
    - "Artist ft. Other"
    - "Artist feat. Other"
    - "Artist, Other, Another"
    - "Artist & Other"
    """
    # Remove everything after "ft.", "feat.", "featuring"
    artist_name = re.split(r'\s+ft\.|\s+ft\s|\s+feat\.|\s+feat\s|\s+featuring\s', artist_name, flags=re.IGNORECASE)[0]
    
    # Remove everything after comma
    artist_name = artist_name.split(',')[0]
    
    # Clean up whitespace
    artist_name = artist_name.strip()
    
    return artist_name

def search_song_release(song_name, artist_name):
    """First try: Search for song as a release/single"""
    url = 'https://api.discogs.com/database/search'
    params = {
        'q': f'{song_name} {artist_name}',
        'type': 'release',
        'format': 'Single'
    }
    
    response = requests.get(url, headers=headers, params=params)
    time.sleep(1)
    
    if response.status_code == 200:
        results = response.json()
        return results['results']
    return []

def search_artist(artist_name):
    """Search for artist ID"""
    url = 'https://api.discogs.com/database/search'
    params = {
        'q': artist_name,
        'type': 'artist'
    }
    
    response = requests.get(url, headers=headers, params=params)
    time.sleep(1)
    
    if response.status_code == 200:
        results = response.json()
        if results['results']:
            return results['results'][0]['id']
    return None

def get_artist_masters(artist_id):
    """Get all master releases (albums) for an artist"""
    url = f'https://api.discogs.com/artists/{artist_id}/releases'
    params = {
        'per_page': 100,
        'sort': 'year',
        'sort_order': 'desc'
    }
    
    response = requests.get(url, headers=headers, params=params)
    time.sleep(1)
    
    if response.status_code == 200:
        data = response.json()
        # Filter for albums/masters
        masters = [r for r in data['releases'] if r.get('type') in ['master', 'release']]
        return masters
    return []

def get_master_details(master_id):
    """Get master release details including tracklist"""
    url = f'https://api.discogs.com/masters/{master_id}'
    
    response = requests.get(url, headers=headers)
    time.sleep(1)
    
    if response.status_code == 200:
        return response.json()
    return None

def get_release_details(release_id):
    """Get release details including genres and styles"""
    url = f'https://api.discogs.com/releases/{release_id}'
    
    response = requests.get(url, headers=headers)
    time.sleep(1)
    
    if response.status_code == 200:
        data = response.json()
        return {
            'genres': data.get('genres', []),
            'styles': data.get('styles', []),
            'tracklist': data.get('tracklist', [])
        }
    return None

def find_song_in_tracklist(tracklist, song_name):
    """Check if song exists in album tracklist"""
    song_lower = song_name.lower()
    for track in tracklist:
        track_title = track.get('title', '').lower()
        # Simple matching - you might want to make this more sophisticated
        if song_lower in track_title or track_title in song_lower:
            return True
    return False

def get_song_genre_style(song_name, artist_name):
    """
    Main function: Try to find genre/style for a song
    1. First search for song as single/release
    2. If not found, search artist's masters/albums
    """
    # Clean the artist name first
    cleaned_artist = clean_artist_name(artist_name)
    print(f"\nSearching for: {song_name} by {artist_name}")
    print(f"  Using cleaned artist name: {cleaned_artist}")
    
    # Step 1: Try direct song search
    results = search_song_release(song_name, cleaned_artist)
    
    if results and len(results) > 0:
        print(f"  Found as single/release")
        release_id = results[0]['id']
        details = get_release_details(release_id)
        if details:
            return {
                'genres': details['genres'],
                'styles': details['styles']
            }
    
    # Step 2: Search through artist's masters
    print(f"  Not found as single, searching artist's albums...")
    artist_id = search_artist(cleaned_artist)
    
    if not artist_id:
        print(f"  Artist not found")
        return None
    
    masters = get_artist_masters(artist_id)
    print(f"  Found {len(masters)} releases for artist")
    
    # Search through each master/album
    for master in masters:
        master_id = master.get('id')
        master_title = master.get('title', '')
        
        # Get master details
        if master.get('type') == 'master':
            details = get_master_details(master_id)
        else:
            details = get_release_details(master_id)
        
        if not details:
            continue
        
        # Check if song is in tracklist
        tracklist = details.get('tracklist', [])
        if find_song_in_tracklist(tracklist, song_name):
            print(f"  Found in album: {master_title}")
            return {
                'genres': details.get('genres', []),
                'styles': details.get('styles', [])
            }
    
    print(f"  Song not found in any releases")
    return None

def process_csv(input_file='obs_3.csv', output_file='obs_3.csv'):
    """
    Read songs from CSV, get genre/style info, and write back
    """
    # Read the input CSV
    songs = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            songs.append(row)
    
    print(f"Loaded {len(songs)} songs from {input_file}")
    
    # Process each song
    for i, song in enumerate(songs, 1):
        print(f"\nProcessing {i}/{len(songs)}: {song['song']} by {song['artist']}")
        
        result = get_song_genre_style(song['song'], song['artist'])
        
        if result:
            # Convert lists to semicolon-delimited strings
            song['discogs_genre'] = '; '.join(result['genres']) if result['genres'] else 'None'
            song['discogs_style'] = '; '.join(result['styles']) if result['styles'] else 'None'
            print(f"  Genres: {song['discogs_genre']}")
            print(f"  Styles: {song['discogs_style']}")
        else:
            song['discogs_genre'] = 'None'
            song['discogs_style'] = 'None'
            print(f"  No data found")
    
    # Write back to CSV
    fieldnames = ['song', 'artist', 'discogs_genre', 'discogs_style']
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(songs)
    
    print(f"\n✓ Saved results to {output_file}")
    
    # Print summary
    found = sum(1 for s in songs if s['discogs_genre'] or s['discogs_style'])
    print(f"\nSummary:")
    print(f"  Total songs: {len(songs)}")
    print(f"  Found genre/style: {found}")
    print(f"  Not found: {len(songs) - found}")

if __name__ == "__main__":
    process_csv('obs_3.csv', 'obs_3.csv')