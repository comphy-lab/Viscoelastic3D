/**
 * @file dropImpact3D.c
 * @brief This file contains the simulation code for the drop impact on a solid surface in 3D. 
 * @author Vatsal Sanjay
 * @version 0.1
 * @date Oct 17, 2024
*/


#include "grid/quadtree.h"
#include "navier-stokes/centered.h"
#define FILTERED // Smear density and viscosity jumps
#include "two-phase.h"
// #include "../src-local/two-phaseVE.h"
// #include "../src-local/log-conform-viscoelastic-3D.h"
#include "navier-stokes/conserving.h"
#include "tension.h"

#define tsnap (1e-1)

// Error tolerancs
#define fErr (1e-3)                                 // error tolerance in f1 VOF
#define KErr (1e-6)                                 // error tolerance in VoF curvature calculated using heigh function method (see adapt event)
#define VelErr (1e-2)                               // error tolerances in velocity -- Use 1e-2 for low Oh and 1e-3 to 5e-3 for high Oh/moderate to high J

#define xDist (5e-2)
#define R2(x,y,z)  (sq(x-1.-xDist) + sq(y) + sq(z))

// boundary conditions
// u.t[left] = dirichlet(0.); // todo: later on use no-slip. For testing, free-slip is faster.
// u.r[left] = dirichlet(0.); // todo: later on use no-slip. For testing, free-slip is faster.
f[left] = dirichlet(0.0);

int MAXlevel;
// We -> Weber number of the drop
// Oh -> Solvent Ohnesorge number
// Oha -> air Ohnesorge number
// De -> Deborah number
// Ec -> Elasto-capillary number
// for now there is no viscoelasticity

double We, Oh, Oha, De, Ec, tmax;
char nameOut[80], dumpFile[80];

int main(int argc, char const *argv[]) {

  L0 = 4.0;
  
  // Values taken from the terminal
  MAXlevel = 6;
  tmax = 3.0;
  We = 5.0;
  Oh = 1e-2;
  De = 1e-2;
  Ec = 1e-2;

  init_grid (1 << 4);

  // Create a folder named intermediate where all the simulation snapshots are stored.
  char comm[80];
  sprintf (comm, "mkdir -p intermediate");
  system(comm);
  // Name of the restart file. See writingFiles event.
  sprintf (dumpFile, "dump");


  rho1 = 1., rho2 = 1e-3;
  Oha = 1e-2 * Oh;
  mu1 = Oh/sqrt(We), mu2 = Oha/sqrt(We);
  G1 = Ec/We, G2 = 0.0;
  lambda1 = De*sqrt(We), lambda2 = 0.0;
  
  f.sigma = 1.0/We;

  run();

}

event init (t = 0) {
  if (!restore (file = dumpFile)){
   refine(R2(x,y,z) < (1.1) && R2(x,y,z) > (0.9) && level < MAXlevel);
   fraction (f, (1-R2(x,y,z)));
   foreach(){
    u.x[] = -f[]*1.0;
   }
  }
}

/**
## Adaptive Mesh Refinement
*/
event adapt(i++){
  scalar KAPPA[];
  curvature(f, KAPPA);
  adapt_wavelet ((scalar *){f, u.x, u.y, KAPPA},
      (double[]){fErr, VelErr, VelErr, KErr},
      MAXlevel, 4);
}

/**
## Dumping snapshots
*/
event writingFiles (t = 0; t += tsnap; t <= tmax) {
  dump (file = dumpFile);
  sprintf (nameOut, "intermediate/snapshot-%5.4f", t);
  dump(file=nameOut);
}

/**
## Ending Simulation
*/
event end (t = end) {
  if (pid() == 0)
    fprintf(ferr, "Level %d, Oh %2.1e\n", MAXlevel, Oh);
}

/**
## Log writing
*/
event logWriting (i++) {

  fprintf(ferr, "i %d, t %g\n", i, t);

  double ke = 0.;
  foreach (reduction(+:ke)){
    ke += (2*pi*y)*(0.5*rho(f[])*(sq(u.x[]) + sq(u.y[])))*sq(Delta);
  }

  static FILE * fp;
  if (pid() == 0) {
    const char* mode = (i == 0) ? "w" : "a";
    fp = fopen("log", mode);
    if (fp == NULL) {
      fprintf(ferr, "Error opening log file\n");
      return 1;
    }

    if (i == 0) {
      fprintf(ferr, "Level %d, Oh %2.1e, Oha %2.1e\n", MAXlevel, Oh, Oha);
      fprintf(ferr, "i dt t ke\n");
      fprintf(fp, "Level %d, Oh %2.1e, Oha %2.1e\n", MAXlevel, Oh, Oha);
      fprintf(fp, "i dt t ke rM\n");
    }

    fprintf(fp, "%d %g %g %g\n", i, dt, t, ke);
    fprintf(ferr, "%d %g %g %g\n", i, dt, t, ke);

    fflush(fp);
    fclose(fp);
  }

  assert(ke > -1e-10);

  if (i > 1e1 && pid() == 0) {
    if (ke > 1e2 || ke < 1e-8) {
      const char* message = (ke > 1e2) ? 
        "The kinetic energy blew up. Stopping simulation\n" : 
        "kinetic energy too small now! Stopping!\n";
      
      fprintf(ferr, "%s", message);
      
      fp = fopen("log", "a");
      fprintf(fp, "%s", message);
      fflush(fp);
      fclose(fp);
      
      dump(file=dumpFile);
      return 1;
    }
  }

}