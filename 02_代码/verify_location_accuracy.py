"""定位精度、县界及坐标转换回归；使用固定坐标，不获取用户实际位置。"""
import unittest
from unittest.mock import patch
import region_lookup as r

def square(x,y,size):return [[x,y],[x+size,y],[x+size,y+size],[x,y+size],[x,y]]

class Location(unittest.TestCase):
 def test_coarse_network_fix_is_not_assigned_to_county(self):
  for accuracy in [1001,3000,9999]:self.assertEqual(r.locate(108.305,22.833,accuracy),('','low_accuracy'))
 def test_known_wuming_interior_point_and_xixiangtang_are_different(self):
  self.assertEqual(r.locate(108.277,23.157,30),('450110','granted'))
  self.assertEqual(r.locate(108.305,22.833,30),('450107','granted'))
 def test_uncertainty_crossing_boundary_is_not_assigned(self):
  with patch.object(r,'gcj',side_effect=lambda x,y:(x,y)),patch.object(r,'boundaries',return_value={'450110':[square(108,23,1)]}):
   self.assertEqual(r.locate(108.0005,23.5,30),('','boundary_uncertain'))
   self.assertEqual(r.locate(108.005,23.5,600),('','boundary_uncertain'))
   self.assertEqual(r.locate(108.5,23.5,600),('450110','granted'))
 def test_overlap_does_not_take_first_county(self):
  data={'450110':[square(108,23,1)],'450107':[square(108.2,23.2,1)]}
  with patch.object(r,'gcj',side_effect=lambda x,y:(x,y)),patch.object(r,'boundaries',return_value=data):
   self.assertEqual(r.locate(108.5,23.5,10),('','boundary_uncertain'))
 def test_enclosed_hole_not_assigned_to_outer_county(self):
  data={'450110':[square(108,23,1),square(108.2,23.2,.6)],'450107':[square(108.2,23.2,.6)]}
  with patch.object(r,'gcj',side_effect=lambda x,y:(x,y)),patch.object(r,'boundaries',return_value=data):
   self.assertEqual(r.locate(108.5,23.5,10),('450107','granted'))
 def test_coordinate_conversion_is_applied_exactly_once(self):
  with patch.object(r,'gcj',wraps=r.gcj) as transform:
   r.locate(108.277,23.157,30);transform.assert_called_once_with(108.277,23.157)
 def test_invalid_accuracy_and_coordinates_rejected(self):
  for point in [(108,23,float('nan')),(True,23,10),(108,23,-1),(181,23,10)]:
   with self.assertRaises(ValueError):r.locate(*point)

if __name__=='__main__':unittest.main(verbosity=2)
