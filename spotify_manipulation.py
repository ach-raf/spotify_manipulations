import math
import time
import configparser
import pandas as pd
import spotipy
import spotipy.util as util
from spotipy.oauth2 import SpotifyClientCredentials


def get_credentials(file_path):
    config = configparser.ConfigParser()
    config.read(file_path)
    credentials = []
    for section in config.sections():
        for key in config[section]:
            # print(f'{key} = {config[section][key]}')
            credentials.append(config[section][key])
    return credentials[0], credentials[1], credentials[2]


def spotify_auth(_spotify_username, _client_id, _client_secret):
    scope = 'playlist-read-collaborative playlist-read-private playlist-modify-private ' \
            'playlist-modify-public user-library-read user-top-read user-library-modify'
    redirect_uri = "http://localhost/"
    token = util.prompt_for_user_token(_spotify_username, scope, client_id=_client_id,
                                       client_secret=_client_secret, redirect_uri=redirect_uri)
    client_credentials_manager = SpotifyClientCredentials(client_id=_client_id,
                                                          client_secret=_client_secret)
    try:
        if token:
            return spotipy.Spotify(client_credentials_manager=client_credentials_manager, auth=token)
    except ConnectionRefusedError:
        print(f'could not get token for {_spotify_username}')


# ++++============================================================++++
#                          Authentication

# get spotify info from the credentials.ini file
spotify_username, client_id, client_secret = get_credentials(r'spotify_credentials.ini')
# use spoti to interact with the spotipy library
spoti = spotify_auth(spotify_username, client_id, client_secret)

# ++++============================================================++++

def get_song_id(_artist, _song_name):
    query = f'artist:{_artist} track:{_song_name}'
    try:
        return spoti.search(query)['tracks']['items'][0]['id']
    except IndexError:
        return False


def get_artist_id(_artist):
    result = spoti.search(q=_artist, type='artist')
    try:
        uri = result['artists']['items'][0]['uri']
        return uri
    except IndexError:
        print('get_artist_id() list index out of range', IndexError)
        return False


def calculate_total_artists(_max_levels, _similar_artists_number):
    _total_artists = 1
    for _index in range(1, _max_levels):
        _total_artists += int(math.pow(_similar_artists_number, _index))

    print(f'Top level artists {_total_artists}')
    print(f'Total artists {_total_artists * _similar_artists_number + 1}')
    return _total_artists


def get_similar_artists(_artist):
    print(f'finding artists similar to {_artist}')
    try:
        result = spoti.search(q=_artist, type='artist')
        # name = result['artists']['items'][0]['name']
        uri = result['artists']['items'][0]['uri']  # artist uri, opeth example spotify:artist:0ybFZ2Ab08V8hueghSXm6E

        _similar_artists = spoti.artist_related_artists(uri)
        return [_artist['name'] for _artist in _similar_artists['artists']]
    except IndexError:
        print('get_similar_artists() list IndexError', IndexError)
        return False


def get_artist_top_songs(_artist_name, _limit=3):
    _artist_id = get_artist_id(_artist_name)
    if _artist_id:
        query = f'spotify:artist:{_artist_id}'
        top_songs = spoti.artist_top_tracks(query)
        return [song['id'] for song in top_songs['tracks'][:_limit]]
    else:
        return False

def get_artist_similar_tracks(_root_artist, _max_levels, _similar_artists_number):
    # get top songs from artists similar to your _root_artist.
    total_artists = calculate_total_artists(_max_levels, _similar_artists_number)
    _artists = [_root_artist]
    _tracks = []
    for _index in range(0, total_artists):
        similar_artists = get_similar_artists(_artists[_index])
        # print(f'{_artists[_index]} similar artists {similar_artists}')
        similar_artists_flag = 0
        for _artist in similar_artists:
            if similar_artists_flag == _similar_artists_number:
                break
            if _artist not in _artists:
                _artists.append(_artist)
                _tracks.extend(get_artist_top_songs(_artist))
                similar_artists_flag += 1
    return get_unique_tracks_to_save(_tracks)


def create_playlist(_spotify_username, _playlist_name, _is_public=False):
    _playlist_id = get_playlist_id(_spotify_username, _playlist_name)
    if not _playlist_id:
        _playlist = spoti.user_playlist_create(_spotify_username, _playlist_name, _is_public)
        try:
            if _playlist['id']:
                print(f'playlist {_playlist_name} created for user {_spotify_username}')
                return True
        except BaseException:
            return False
    else:
        print(f'The playlist {_playlist_name} already exists')
        return True


def get_playlist_id(_spotify_username, _playlist_name):
    _playlist_exists = False
    playlists = spoti.user_playlists(_spotify_username)
    for playlist in playlists['items']:
        if _playlist_name == playlist['name']:
            _playlist_exists = True
            return playlist['id']
    if not _playlist_exists:
        return False


def get_playlist_tracks(_spotify_username, _playlist_name):
    _playlist_id = get_playlist_id(_spotify_username, _playlist_name)
    if _playlist_id:
        try:
            results = spoti.user_playlist(_spotify_username, _playlist_id)
            _tracks = []
            for _track in results['tracks']['items']:
                _tracks.append(_track['track']['id'])
            return _tracks
        except IndexError:
            print('IndexError: ', IndexError)
            return False
    else:
        print(f'playlist {_playlist_name} does not exist')
        return False
    

def empty_playlist(_spotify_username, _playlist_name):
    _playlist_id = get_playlist_id(_spotify_username, _playlist_name)
    if _playlist_id:
        # empty a playlist by replacing tracks with an empty list
        result = spoti.user_playlist_replace_tracks(_spotify_username, _playlist_id, [])
        if result:
            print(f'playlist {_playlist_name} was emptied')
            return True
        else:
            print(f'Could not empty the playlist {_playlist_name}')
            return False
    else:
        print(f'playlist {_playlist_name} does not exist')
        return False


def save_to_playlist(_spotify_username, _playlist_name, _tracks):
    if not get_playlist_id(_spotify_username, _playlist_name):
        create_playlist(_spotify_username, _playlist_name)
    try:
        # check if there is existing tracks
        _playlist_tracks = get_playlist_tracks(_spotify_username, _playlist_name)
    except TypeError:
        _playlist_tracks = []
    _unique_tracks = get_unique_tracks_to_save(_playlist_tracks, _tracks)
    if _unique_tracks:
        _playlist_id = get_playlist_id(_spotify_username, _playlist_name)
        # spotify API can only allow 100 requests at time, so we create chuncks to avoid that limit.
        _max_request = 100
        chunks = [_unique_tracks[i:i + _max_request] for i in range(0, len(_unique_tracks), _max_request)]
        for chunk in chunks:
            spoti.user_playlist_add_tracks(_spotify_username, _playlist_id, chunk, position=None)
            print('Playlist is populated with new songs !!')
    else:
        print('No new songs added')


def get_unique_tracks_to_save(_existing_tracks, _new_tracks):
    if set(_existing_tracks) == set(_new_tracks):
        print('The playlists are the same')
        return False
    else:
        # remove duplicates
        _new_tracks = list(set(_new_tracks))
        # keep only new tracks in unique tracks
        _unique_tracks = [track for track in _new_tracks if track not in _existing_tracks]
        return _unique_tracks


def shazamCSV_to_spotify(_shazam_csv_file, _playlist_name):
    shazam_data = pd.DataFrame(pd.read_csv(_shazam_csv_file, skiprows=[0], usecols=['Artist', 'Title']))
    _shazam_songs = []

    for index, row in shazam_data.iterrows():
        _song_id = get_song_id(row['Artist'], row['Title'])
        if _song_id:
            print(f"{index} - {row['Artist']} - {row['Title']}")
            _shazam_songs.append(_song_id)

    playlist_created = create_playlist(spotify_username, _playlist_name)
    if playlist_created:
        save_to_playlist(spotify_username, _playlist_name, _shazam_songs)
    else:
        print('Error could not create the playlist')
        



"""
# get top songs from artists similar to your choice:
# using default values (limit of top 3 songs for each artist for example), this will give us 31 artists, and 89 songs.
max_levels = 4  # 4 how many levels you'll go down
similar_artists_number = 2  # 2 how many similar artist for each artist
playlist_name = 'doors_sim'
artist_name = 'the doors'
similar_tracks = get_artist_similar_tracks(artist_name, max_levels, similar_artists_number)
save_to_playlist(spotify_username, playlist_name, similar_tracks)
"""

"""
# get artist top songs

playlist_name = 'the_doors_top_10'
artist_name = 'the doors'
artist_top_songs = get_artist_top_songs(artist_name, 10)
save_to_playlist(spotify_username, playlist_name, artist_top_songs)
"""

"""
# Shazam example:
csv_file = 'shazamlibrary.csv'
playlist_name = 'my_shazam'
shazamCSV_to_spotify(csv_file, playlist_name)
"""

