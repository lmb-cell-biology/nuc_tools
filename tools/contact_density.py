import sys,  os, math
import numpy as np


PROG_NAME = 'contact_density'
VERSION = '1.0.0'
DESCRIPTION = 'Creates linear contact density data tracks, in BED format, from 2D Hi-C data for different sequence separation ranges and in trans'
SEQ_SEP_THRESHOLDS = [int(1e5), int(1e6), int(1e7)]
DEFAULT_BIN_SIZE = 25.0


# Ad an all cis counts track cis

def contact_density(contact_path, out_path_root=None, bin_size=DEFAULT_BIN_SIZE, seq_sep_thresholds=SEQ_SEP_THRESHOLDS):

  from nuc_tools import util, io
  from formats import ncc, npz, bed
    
  if  out_path_root:
    out_path_root = os.path.splitext(out_path_root)[0]
  else:
    out_path_root = os.path.splitext(contact_path)[0] + '_contact_density'
  
  util.info('  .. loading')
  
  if io.is_ncc(contact_path):
    file_bin_size = None
    bin_size = int(bin_size * 1e3)
    util.info('  .. loading')
    chromosomes, chromo_limits, contacts = ncc.load_file(in_path, trans=True, dtype=np.int32)
    
  else:
    file_bin_size, chromo_limits, contacts = npz.load_npz_contacts(contact_path, trans=True)
    bin_size = file_bin_size
    chromosomes = chromo_limits.keys()
  
  chromosomes = util.sort_chromosomes(chromosomes)
  
  n_tracks = len(SEQ_SEP_THRESHOLDS) + 3 # Add very big, plus all cis, plus trans
  
  data_tracks = []
  
  for i in range(n_tracks):
    data_dict = {}
    
    for chromo in chromosomes:
      start, end = chromo_limits[chromo] # starts might not be on-bin
      n_bins = int(math.ceil(end/float(bin_size)))
      data_dict[chromo] = np.zeros(n_bins)
  
    data_tracks.append(data_dict)
  
  thr_max_min = ((SEQ_SEP_THRESHOLDS[0], None),
                 (SEQ_SEP_THRESHOLDS[1], SEQ_SEP_THRESHOLDS[0]),
                 (SEQ_SEP_THRESHOLDS[2], SEQ_SEP_THRESHOLDS[1]),
                 (None, SEQ_SEP_THRESHOLDS[2]),
                 (None, None))
                 
  track_tags = []
  for mx, mn in thr_max_min:
    if mx and mn:
      tag = '%d-%dk' % (mn/1e3, mx/1e3)
    elif mx:
      tag = '0-%dk' % (mx/1e3,)
    elif mn:
      tag = '%dk+' % (mn/1e3)
    else:
      tag = 'cis'
      
    track_tags.append(tag)
    
  track_tags.append('trans')  
  
  for chr_a, chr_b in contacts:
    chromo_pair= (chr_a, chr_b)
    n_a = len(data_tracks[0][chr_a])
    n_b = len(data_tracks[0][chr_b])
    
    if file_bin_size:
      matrix = contacts[chromo_pair]
      
      if chr_a == chr_b: # cis
        n = len(matrix)
        data_idx = 0
 
        for d in range(0, n): # diagonal line
          m = n-d
          rows = np.array(range(m))
          cols = rows + d
          idx = (rows, cols)
          seq_sep = d * file_bin_size
       
          if d and (seq_sep >= SEQ_SEP_THRESHOLDS[data_idx]) and ((d-1) * file_bin_size < SEQ_SEP_THRESHOLDS[data_idx]):
            data_idx += 1
          
          data_dict = data_tracks[data_idx]
          data_dict[chr_a][:m] += matrix[idx] # rows
          data_dict[chr_a][d:] += matrix[idx] # cols
        
        # all cis
        data_dict = data_tracks[-2]
        data_dict[chr_a] += matrix.sum(axis=1)
        data_dict[chr_b] += matrix.sum(axis=0)        
        
      else: # trans
        data_dict = data_tracks[-1]
        data_dict[chr_a] += matrix.sum(axis=1)
        data_dict[chr_b] += matrix.sum(axis=0)
     
    else:
      contact_array = contacts[chromo_pair]
      seq_pos_a = contact_array[:,0]
      seq_pos_b = contact_array[:,1]
      chromo_counts = contact_array[:,2]
      seps = abs(seq_pos_a-seq_pos_b)
      
      bins_a = (seq_pos_a/bin_size).astype(int)
      bins_b = (seq_pos_b/bin_size).astype(int)
      
      if chr_a == chr_b:
        for i, (th_max, th_min) in enumerate(thr_max_min): # Short/long range seq separation limits
          if th_max and th_min:
            idx = seps < th_max & seps >= th_min
          elif th_max:
            idx = seps < th_max
          elif th_min:
            idx = seps >= th_min
          else:
            idx = seps > 0
          
          bin_counts_a, null = np.histogram(bins_a[idx], bins=n_a, range=(0,n_a))
          bin_counts_b, null = np.histogram(bins_b[idx], bins=n_b, range=(0,n_b))
          data_dict = data_tracks[i]
          data_dict[chr_a] += bin_counts_a
          data_dict[chr_a] += bin_counts_b
        
      else:
        bin_counts_a, null = np.histogram(bins_a, bins=n_a, range=(0,n_a))
        bin_counts_b, null = np.histogram(bins_b, bins=n_b, range=(0,n_b))
        data_dict = data_tracks[-1]
        data_dict[chr_a][bins_a] += bin_counts_a
        data_dict[chr_b][bins_a] += bin_counts_b
  
  for i, data_dict in enumerate(data_tracks):
    out_file_path = '{}_{}.bed'.format(out_path_root, track_tags[i])
    total = 0
    
    for chromo in data_dict:
      hist = data_dict[chromo]
      idx = hist.nonzero()[0]
      pos = np.arange(0, len(hist)*bin_size, bin_size)[idx]
      values = hist[idx]
      n = len(idx)

      track = np.zeros(n, dtype=util.DATA_TRACK_TYPE)
      track['pos1'] = pos
      track['pos2'] = pos+bin_size-1
      track['strand'] = np.ones(n)
      track['value'] = values
      track['orig_value'] = values[:]
   
      data_dict[chromo] = track
      total += n
    
    print i, total
    if total:
      bed.save_data_track(out_file_path, data_dict, scale=1.0, as_float=False)
      util.info('Written {} regions to {}'.format(total, out_file_path))   
    
    
def main(argv=None):

  from argparse import ArgumentParser
  from nuc_tools import util, io
  
  if argv is None:
    argv = sys.argv[1:]

  epilog = 'For further help email tjs23@cam.ac.uk or wb104@cam.ac.uk'

  arg_parse = ArgumentParser(prog=PROG_NAME, description=DESCRIPTION,
                             epilog=epilog, prefix_chars='-', add_help=True)

  arg_parse.add_argument(metavar='CONTACT_FILE', dest='i',
                         help='Input NPZ or NCC format chromatin contact file.')

  arg_parse.add_argument('-s', '--bin-size', default=DEFAULT_BIN_SIZE, metavar='BIN_SIZE', type=float, dest="s",
                         help='For NCC format input, the binned region size for output data track, in kilobases. ' \
                              'Defaults to %.1f kb but not not used if NPZ data is input: here the native bin size of the contact map is used.' % DEFAULT_BIN_SIZE)

  arg_parse.add_argument('-o', '--out-file-root',metavar='OUT_FILE_ROOT', dest='o',
                         help='Optional file path to specify where output data track files will be saved.' \
                              'All output file names will be appended with the different sequence separation thresholds.')
  
 
  args = vars(arg_parse.parse_args(argv))

  contact_path = args['i']
  out_path_root = args['o']
  bin_size = args['s']
  
  io.check_invalid_file(contact_path)  
  
  contact_density(contact_path, out_path_root, bin_size)
  

if __name__ == "__main__":
  sys.path.append(os.path.dirname(os.path.dirname(__file__)))
  main()

