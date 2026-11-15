// Electronics-only Pura enclosure. UNPOWERED FIT-CHECK DRAFT.
// All mm. Change part to base, lid, keeper, board_gauge, plug_gauge, assembly.
part = "assembly";
$fn = 128;
board_d = 84.67;
board_t = 1.7;
hole_spacing = 42.8;
hole_y_from_led_edge = 29.5;
// Assumes holes symmetric and LED edge at the full circular envelope.
hole_y = board_d/2-hole_y_from_led_edge;
wall = 2.4;
inner_r = board_d/2+1.4;
outer_r = inner_r+wall;
board_bottom = 14.4;
seam = 32.4;
lid_t = 2.4;
plug_y = -26; // PROVISIONAL: check against real PCB notch and plug assembly.
plug_flange_d = 29.84;
plug_neck_d = 25.7;
plug_flange_t = 5;
plug_total_t = 11.8;
plug_seat_top = wall+plug_flange_t;
fit_allowance_d = .2; // flange confirmed; neck estimated for test fit.

module at_holes() {for(x=[-hole_spacing/2,hole_spacing/2]) translate([x,hole_y,0]) children();}
module at_ears() {for(x=[-49,49]) translate([x,0,0]) children();}
module at_plug_screws(){for(a=[45,135,225,315]) translate([17.5*cos(a),plug_y+17.5*sin(a),0])children();}
module cylinder_z(r,z0,z1){translate([0,0,z0])cylinder(r=r,h=z1-z0);}
module footprint_ears(h){
  for(x=[-49,49]) {
    translate([x,0,0])cylinder(r=4.8,h=h);
    translate([x-sign(x)*3,0,h/2])cube([7,8,h],center=true);
  }
}
module sensor_cut(){
  a=-138.628735075; // moved 15 mm toward 8 oclock along outer arc
  translate([(inner_r+wall/2)*cos(a),(inner_r+wall/2)*sin(a),15.25])
    rotate([0,90,a])cylinder(r=4,h=16,center=true);
}
module led_cuts(){
  for(a=[141.209578358,120.725747015,99.000000000,81.000000000,59.274252985,38.790421642])
    translate([(inner_r+wall/2)*cos(a),(inner_r+wall/2)*sin(a),15.25])
      rotate([0,90,a])cylinder(r=3,h=16,center=true);
}
module base(){difference(){
  union(){
    difference(){cylinder(r=outer_r,h=seam);cylinder_z(inner_r,wall,seam+1);}
    footprint_ears(seam);
    at_holes(){cylinder_z(4,wall,board_bottom);cylinder_z(2.65,board_bottom,board_bottom+1.7);}
    translate([0,plug_y,0])cylinder(r=17.5,h=plug_seat_top);
    at_plug_screws()cylinder_z(3.2,wall,plug_seat_top);
  }
  translate([0,plug_y,0]){
    cylinder_z((plug_neck_d+fit_allowance_d)/2,-1,plug_seat_top+1);
    cylinder_z((plug_flange_d+fit_allowance_d)/2,wall,plug_seat_top+1);
  }
  at_holes()cylinder_z(1,board_bottom-6,board_bottom+2);
  at_ears()cylinder_z(1.25,seam-9,seam+1);
  at_plug_screws()cylinder_z(.8,3.4,plug_seat_top+1);
  sensor_cut();
  led_cuts();
}}
module lid(){difference(){
  union(){
    cylinder(r=outer_r,h=lid_t);footprint_ears(lid_t);
    difference(){cylinder_z(inner_r-.25,lid_t,lid_t+2.5);cylinder_z(inner_r-1.65,lid_t-.1,lid_t+3);}
  }
  at_ears()cylinder_z(1.65,-1,lid_t+1);
}}
module keeper(){translate([0,-plug_y,0])difference(){
  union(){translate([0,plug_y,0])cylinder(r=17.5,h=2.4);at_plug_screws()cylinder(r=3.2,h=2.4);}
  translate([0,plug_y,0])cylinder_z((plug_neck_d+fit_allowance_d)/2,-1,3);
  at_plug_screws()cylinder_z(1.1,-1,3);
}}
module board_gauge(){union(){translate([0,0,1.2])cube([56,14,2.4],center=true);for(x=[-hole_spacing/2,hole_spacing/2])translate([x,0,0]){cylinder_z(4,2.4,14.4);cylinder_z(2.65,14.4,16.1);}}}
// Four holes, left to right, with 0.2, 0.4, 0.6, 0.8 mm diameter clearance.
module plug_gauge(d=plug_neck_d){
 difference(){
  translate([0,0,1.2])cube([142,48,2.4],center=true);
  for(i=[0:3])translate([-51+34*i,4,0])cylinder_z((d+.2+.2*i)/2,-1,4);
 }
 for(i=[0:3])translate([-51+34*i,-19,2.4])linear_extrude(.5)text(str(d+.2+.2*i),size=4,halign="center");
}
if(part=="base")base();
if(part=="lid")lid();
module keeper_half(upper=true){intersection(){
 keeper();translate([0,(upper?1:-1)*25.15,2])cube([100,50,10],center=true);
}}
if(part=="keeper_upper")keeper_half(true);
if(part=="keeper_lower")keeper_half(false);
if(part=="keeper"){translate([0,3,0])keeper_half(true);translate([0,-3,0])keeper_half(false);}
if(part=="board_gauge")board_gauge();
if(part=="plug_gauge" || part=="plug_neck_gauge")plug_gauge(plug_neck_d);
if(part=="plug_flange_gauge")plug_gauge(plug_flange_d);
if(part=="assembly"){
  color("LightSteelBlue")base();
  color("Wheat")translate([0,plug_y,plug_seat_top]){translate([0,2,0])keeper_half(true);translate([0,-2,0])keeper_half(false);}
  color("LightGray",.6)translate([0,0,seam+lid_t+12])rotate([180,0,0])lid();
}
