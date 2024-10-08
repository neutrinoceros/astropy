# Licensed under a 3-clause BSD style license - see LICENSE.rst

# This file was automatically generated from ply. To re-generate this file,
# remove it from this folder, then build astropy and run the tests in-place:
#
#   python setup.py build_ext --inplace
#   pytest astropy/units
#
# You can then commit the changes to this file.


# ogip_parsetab.py
# This file is automatically generated. Do not edit.
# pylint: disable=W,C,R
_tabversion = '3.10'

_lr_method = 'LALR'

_lr_signature = 'CLOSE_PAREN DIVISION FUNCNAME LIT10 OPEN_PAREN SIGN STAR STARSTAR UFLOAT UINT UNIT UNKNOWN WHITESPACE\n            main : UNKNOWN\n                 | complete_expression\n                 | scale_factor complete_expression\n                 | scale_factor WHITESPACE complete_expression\n            \n            complete_expression : product_of_units\n            \n            product_of_units : unit_expression\n                             | function\n                             | division unit_expression\n                             | product_of_units product unit_expression\n                             | product_of_units division unit_expression\n            \n            unit_expression : unit\n                            | UNIT OPEN_PAREN complete_expression CLOSE_PAREN\n                            | OPEN_PAREN complete_expression CLOSE_PAREN\n                            | UNIT OPEN_PAREN complete_expression CLOSE_PAREN power numeric_power\n                            | OPEN_PAREN complete_expression CLOSE_PAREN power numeric_power\n            \n            function : FUNCNAME OPEN_PAREN complete_expression CLOSE_PAREN\n                     | FUNCNAME OPEN_PAREN complete_expression CLOSE_PAREN power numeric_power\n            \n            scale_factor : LIT10 power numeric_power\n                         | LIT10\n                         | signed_float\n                         | signed_float power numeric_power\n                         | signed_int power numeric_power\n            \n            division : DIVISION\n                     | WHITESPACE DIVISION\n                     | WHITESPACE DIVISION WHITESPACE\n                     | DIVISION WHITESPACE\n            \n            product : WHITESPACE\n                    | STAR\n                    | WHITESPACE STAR\n                    | WHITESPACE STAR WHITESPACE\n                    | STAR WHITESPACE\n            \n            power : STARSTAR\n            \n            unit : UNIT\n                 | UNIT power numeric_power\n            \n            numeric_power : UINT\n                          | signed_float\n                          | OPEN_PAREN signed_int CLOSE_PAREN\n                          | OPEN_PAREN signed_float CLOSE_PAREN\n                          | OPEN_PAREN signed_float division UINT CLOSE_PAREN\n            \n            sign : SIGN\n                 |\n            \n            signed_int : SIGN UINT\n            \n            signed_float : sign UINT\n                         | sign UFLOAT\n            '
    
_lr_action_items = {'UNKNOWN':([0,],[2,]),'LIT10':([0,],[7,]),'SIGN':([0,27,28,29,30,36,50,63,68,70,],[14,51,-32,51,51,51,14,51,51,51,]),'UNIT':([0,4,7,8,12,17,19,21,22,23,24,25,26,32,33,35,38,39,41,42,45,46,47,48,49,52,53,58,59,65,66,74,],[16,16,-19,-20,16,16,-23,16,-24,16,16,-27,-28,-43,-44,16,16,-26,-23,-25,-29,-31,-18,-35,-36,-21,-22,-25,-30,-37,-38,-39,]),'OPEN_PAREN':([0,4,7,8,12,16,17,18,19,21,22,23,24,25,26,27,28,29,30,32,33,35,36,38,39,41,42,45,46,47,48,49,52,53,58,59,63,65,66,68,70,74,],[17,17,-19,-20,17,35,17,38,-23,17,-24,17,17,-27,-28,50,-32,50,50,-43,-44,17,50,17,-26,-23,-25,-29,-31,-18,-35,-36,-21,-22,-25,-30,50,-37,-38,50,50,-39,]),'FUNCNAME':([0,4,7,8,17,21,32,33,35,38,47,48,49,52,53,65,66,74,],[18,18,-19,-20,18,18,-43,-44,18,18,-18,-35,-36,-21,-22,-37,-38,-39,]),'DIVISION':([0,4,5,6,7,8,10,11,15,16,17,21,25,31,32,33,35,38,43,44,47,48,49,52,53,55,56,61,62,64,65,66,69,72,73,74,],[19,19,22,19,-19,-20,-6,-7,-11,-33,19,41,22,-8,-43,-44,19,19,-9,-10,-18,-35,-36,-21,-22,-34,-13,19,-12,-16,-37,-38,-15,-14,-17,-39,]),'WHITESPACE':([0,4,6,7,8,10,11,15,16,17,19,21,22,26,31,32,33,35,38,41,43,44,45,47,48,49,52,53,55,56,61,62,64,65,66,69,72,73,74,],[5,21,25,-19,-20,-6,-7,-11,-33,5,39,5,42,46,-8,-43,-44,5,5,58,-9,-10,59,-18,-35,-36,-21,-22,-34,-13,5,-12,-16,-37,-38,-15,-14,-17,-39,]),'UINT':([0,13,14,19,22,27,28,29,30,36,39,42,50,51,63,67,68,70,],[-41,32,34,-23,-24,48,-32,48,48,48,-26,-25,-41,-40,48,71,48,48,]),'UFLOAT':([0,13,14,27,28,29,30,36,50,51,63,68,70,],[-41,33,-40,-41,-32,-41,-41,-41,-41,-40,-41,-41,-41,]),'$end':([1,2,3,6,10,11,15,16,20,31,32,33,40,43,44,48,49,55,56,62,64,65,66,69,72,73,74,],[0,-1,-2,-5,-6,-7,-11,-33,-3,-8,-43,-44,-4,-9,-10,-35,-36,-34,-13,-12,-16,-37,-38,-15,-14,-17,-39,]),'CLOSE_PAREN':([6,10,11,15,16,31,32,33,34,37,43,44,48,49,54,55,56,57,60,61,62,64,65,66,69,71,72,73,74,],[-5,-6,-7,-11,-33,-8,-43,-44,-42,56,-9,-10,-35,-36,62,-34,-13,64,65,66,-12,-16,-37,-38,-15,74,-14,-17,-39,]),'STAR':([6,10,11,15,16,25,31,32,33,43,44,48,49,55,56,62,64,65,66,69,72,73,74,],[26,-6,-7,-11,-33,45,-8,-43,-44,-9,-10,-35,-36,-34,-13,-12,-16,-37,-38,-15,-14,-17,-39,]),'STARSTAR':([7,8,9,16,32,33,34,56,62,64,],[28,28,28,28,-43,-44,-42,28,28,28,]),}

_lr_action = {}
for _k, _v in _lr_action_items.items():
   for _x,_y in zip(_v[0],_v[1]):
      if not _x in _lr_action:  _lr_action[_x] = {}
      _lr_action[_x][_k] = _y
del _lr_action_items

_lr_goto_items = {'main':([0,],[1,]),'complete_expression':([0,4,17,21,35,38,],[3,20,37,40,54,57,]),'scale_factor':([0,],[4,]),'product_of_units':([0,4,17,21,35,38,],[6,6,6,6,6,6,]),'signed_float':([0,27,29,30,36,50,63,68,70,],[8,49,49,49,49,61,49,49,49,]),'signed_int':([0,50,],[9,60,]),'unit_expression':([0,4,12,17,21,23,24,35,38,],[10,10,31,10,10,43,44,10,10,]),'function':([0,4,17,21,35,38,],[11,11,11,11,11,11,]),'division':([0,4,6,17,21,35,38,61,],[12,12,24,12,12,12,12,67,]),'sign':([0,27,29,30,36,50,63,68,70,],[13,13,13,13,13,13,13,13,13,]),'unit':([0,4,12,17,21,23,24,35,38,],[15,15,15,15,15,15,15,15,15,]),'product':([6,],[23,]),'power':([7,8,9,16,56,62,64,],[27,29,30,36,63,68,70,]),'numeric_power':([27,29,30,36,63,68,70,],[47,52,53,55,69,72,73,]),}

_lr_goto = {}
for _k, _v in _lr_goto_items.items():
   for _x, _y in zip(_v[0], _v[1]):
       if not _x in _lr_goto: _lr_goto[_x] = {}
       _lr_goto[_x][_k] = _y
del _lr_goto_items
_lr_productions = [
  ("S' -> main","S'",1,None,None,None),
  ('main -> UNKNOWN','main',1,'p_main','ogip.py',169),
  ('main -> complete_expression','main',1,'p_main','ogip.py',170),
  ('main -> scale_factor complete_expression','main',2,'p_main','ogip.py',171),
  ('main -> scale_factor WHITESPACE complete_expression','main',3,'p_main','ogip.py',172),
  ('complete_expression -> product_of_units','complete_expression',1,'p_complete_expression','ogip.py',183),
  ('product_of_units -> unit_expression','product_of_units',1,'p_product_of_units','ogip.py',189),
  ('product_of_units -> function','product_of_units',1,'p_product_of_units','ogip.py',190),
  ('product_of_units -> division unit_expression','product_of_units',2,'p_product_of_units','ogip.py',191),
  ('product_of_units -> product_of_units product unit_expression','product_of_units',3,'p_product_of_units','ogip.py',192),
  ('product_of_units -> product_of_units division unit_expression','product_of_units',3,'p_product_of_units','ogip.py',193),
  ('unit_expression -> unit','unit_expression',1,'p_unit_expression','ogip.py',207),
  ('unit_expression -> UNIT OPEN_PAREN complete_expression CLOSE_PAREN','unit_expression',4,'p_unit_expression','ogip.py',208),
  ('unit_expression -> OPEN_PAREN complete_expression CLOSE_PAREN','unit_expression',3,'p_unit_expression','ogip.py',209),
  ('unit_expression -> UNIT OPEN_PAREN complete_expression CLOSE_PAREN power numeric_power','unit_expression',6,'p_unit_expression','ogip.py',210),
  ('unit_expression -> OPEN_PAREN complete_expression CLOSE_PAREN power numeric_power','unit_expression',5,'p_unit_expression','ogip.py',211),
  ('function -> FUNCNAME OPEN_PAREN complete_expression CLOSE_PAREN','function',4,'p_function','ogip.py',233),
  ('function -> FUNCNAME OPEN_PAREN complete_expression CLOSE_PAREN power numeric_power','function',6,'p_function','ogip.py',234),
  ('scale_factor -> LIT10 power numeric_power','scale_factor',3,'p_scale_factor','ogip.py',249),
  ('scale_factor -> LIT10','scale_factor',1,'p_scale_factor','ogip.py',250),
  ('scale_factor -> signed_float','scale_factor',1,'p_scale_factor','ogip.py',251),
  ('scale_factor -> signed_float power numeric_power','scale_factor',3,'p_scale_factor','ogip.py',252),
  ('scale_factor -> signed_int power numeric_power','scale_factor',3,'p_scale_factor','ogip.py',253),
  ('division -> DIVISION','division',1,'p_division','ogip.py',268),
  ('division -> WHITESPACE DIVISION','division',2,'p_division','ogip.py',269),
  ('division -> WHITESPACE DIVISION WHITESPACE','division',3,'p_division','ogip.py',270),
  ('division -> DIVISION WHITESPACE','division',2,'p_division','ogip.py',271),
  ('product -> WHITESPACE','product',1,'p_product','ogip.py',277),
  ('product -> STAR','product',1,'p_product','ogip.py',278),
  ('product -> WHITESPACE STAR','product',2,'p_product','ogip.py',279),
  ('product -> WHITESPACE STAR WHITESPACE','product',3,'p_product','ogip.py',280),
  ('product -> STAR WHITESPACE','product',2,'p_product','ogip.py',281),
  ('power -> STARSTAR','power',1,'p_power','ogip.py',287),
  ('unit -> UNIT','unit',1,'p_unit','ogip.py',293),
  ('unit -> UNIT power numeric_power','unit',3,'p_unit','ogip.py',294),
  ('numeric_power -> UINT','numeric_power',1,'p_numeric_power','ogip.py',303),
  ('numeric_power -> signed_float','numeric_power',1,'p_numeric_power','ogip.py',304),
  ('numeric_power -> OPEN_PAREN signed_int CLOSE_PAREN','numeric_power',3,'p_numeric_power','ogip.py',305),
  ('numeric_power -> OPEN_PAREN signed_float CLOSE_PAREN','numeric_power',3,'p_numeric_power','ogip.py',306),
  ('numeric_power -> OPEN_PAREN signed_float division UINT CLOSE_PAREN','numeric_power',5,'p_numeric_power','ogip.py',307),
  ('sign -> SIGN','sign',1,'p_sign','ogip.py',318),
  ('sign -> <empty>','sign',0,'p_sign','ogip.py',319),
  ('signed_int -> SIGN UINT','signed_int',2,'p_signed_int','ogip.py',328),
  ('signed_float -> sign UINT','signed_float',2,'p_signed_float','ogip.py',334),
  ('signed_float -> sign UFLOAT','signed_float',2,'p_signed_float','ogip.py',335),
]
