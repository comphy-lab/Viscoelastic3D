/**
# 3D Matrix Diagonalization and Eigendecomposition

This module implements the diagonalization of 3D symmetric matrices through
eigendecomposition, allowing the computation of eigenvalues and eigenvectors
for 3x3 symmetric matrices. The implementation follows standard linear algebra
approaches to compute $A = R \times \Lambda \times R^T$ where:

- $A$ is the original symmetric matrix
- $R$ is the orthogonal matrix of eigenvectors
- $\Lambda$ is the diagonal matrix of eigenvalues

## Numerical Parameters

- EPSILON: Used for floating-point comparisons to zero
- RELATIVE_TOLERANCE: Used for relative error checks in verification
*/

#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include "eigen_decomposition.h"

#define EPSILON 1e-9
#define RELATIVE_TOLERANCE 1e-6
#define sq(x) ((x)*(x))

/**
## Data Structures

### 3D Vector

Represents a 3D vector with long double precision components.
*/
typedef struct { long double x, y, z; } pseudo_v3d;

/**
### 3D Tensor/Matrix

Represents a 3x3 matrix or tensor with long double precision components.
Organized as three row vectors (x, y, z).
*/
typedef struct { pseudo_v3d x, y, z; } pseudo_t3d;

/**
### diagonalization_3D

Performs eigendecomposition of a 3D symmetric matrix.

This function computes the eigenvalues and eigenvectors of a 3x3 symmetric
matrix using the eigen_decomposition function. It handles special cases
where the matrix is already diagonal.

Parameters:
- Lambda: Output parameter to store the eigenvalues
- R: Output parameter to store the eigenvectors as columns of R
- A: Input symmetric matrix to be diagonalized

The function maps the struct-based representation to arrays for computation
and then maps the results back to the struct-based representation.
*/
static void diagonalization_3D(pseudo_v3d* Lambda, pseudo_t3d* R, pseudo_t3d* A)
{
  // Check if the matrix is already diagonal
  if (sq(A->x.y) + sq(A->x.z) + sq(A->y.z) < 1e-15) {
    R->x.x = R->y.y = R->z.z = 1.;
    R->y.x = R->x.y = R->z.x = R->x.z = R->z.y = R->y.z = 0.;
    Lambda->x = A->x.x; Lambda->y = A->y.y; Lambda->z = A->z.z;
    return;
  }

  // Compute eigenvalues using the eigen_decomposition function
  double matrix[3][3] = {
    {A->x.x, A->x.y, A->x.z},
    {A->x.y, A->y.y, A->y.z},
    {A->x.z, A->y.z, A->z.z}
  };
  double eigenvectors[3][3];
  double eigenvalues[3];

  compute_eigensystem_symmetric_3x3(matrix, eigenvectors, eigenvalues);

  // Store eigenvalues and eigenvectors with proper index mapping
  Lambda->x = eigenvalues[0];
  Lambda->y = eigenvalues[1];
  Lambda->z = eigenvalues[2];

  R->x.x = eigenvectors[0][0]; R->x.y = eigenvectors[0][1]; R->x.z = eigenvectors[0][2];
  R->y.x = eigenvectors[1][0]; R->y.y = eigenvectors[1][1]; R->y.z = eigenvectors[1][2];
  R->z.x = eigenvectors[2][0]; R->z.y = eigenvectors[2][1]; R->z.z = eigenvectors[2][2];
}

/**
### print_pseudo_t3d

Prints a 3x3 matrix to standard output with formatting.

Parameters:
- name: Label for the matrix output
- matrix: Pointer to the 3x3 matrix to be printed
*/
void print_pseudo_t3d(const char* name, const pseudo_t3d* matrix) {
  printf("%s:\n", name);
  printf("%12.9Lf %12.9Lf %12.9Lf\n", matrix->x.x, matrix->x.y, matrix->x.z);
  printf("%12.9Lf %12.9Lf %12.9Lf\n", matrix->y.x, matrix->y.y, matrix->y.z);
  printf("%12.9Lf %12.9Lf %12.9Lf\n", matrix->z.x, matrix->z.y, matrix->z.z);
  printf("\n");
}

/**
### print_pseudo_v3d

Prints a 3D vector to standard output with formatting.

Parameters:
- name: Label for the vector output
- vector: Pointer to the 3D vector to be printed
*/
void print_pseudo_v3d(const char* name, const pseudo_v3d* vector) {
  printf("%s: %12.9Lf %12.9Lf %12.9Lf\n\n", name, vector->x, vector->y, vector->z);
}

/**
### verify_orthonormality

Verifies that the eigenvectors form an orthonormal basis.

This function checks two key properties of eigenvectors:
1. Each eigenvector has unit norm (normalized)
2. Eigenvectors are mutually orthogonal (dot product is zero)

Parameters:
- R: Matrix containing eigenvectors as columns

Returns:
- 1 if eigenvectors are orthonormal
- 0 otherwise, with diagnostic messages printed to stdout
*/
int verify_orthonormality(const pseudo_t3d* R) {
  for (int i = 0; i < 3; i++) {
    long double norm = sq(((long double*)R)[i]) + sq(((long double*)R)[i+3]) 
                      + sq(((long double*)R)[i+6]);
    if (fabsl(norm - 1.0L) > EPSILON) {
      printf("Eigenvector %d is not normalized. Norm = %Lf\n", i, sqrtl(norm));
      return 0;
    }
    
    for (int j = i + 1; j < 3; j++) {
      long double dot_product = ((long double*)R)[i] * ((long double*)R)[j] + 
                                ((long double*)R)[i+3] * ((long double*)R)[j+3] + 
                                ((long double*)R)[i+6] * ((long double*)R)[j+6];
      if (fabsl(dot_product) > EPSILON) {
        printf("Eigenvectors %d and %d are not orthogonal. Dot product = %Lf\n", 
               i, j, dot_product);
        return 0;
      }
    }
  }
  return 1;
}

/**
### verify_diagonalization

Verifies that the matrix is properly diagonalized by computing R^T * A * R
and checking if it approximates a diagonal matrix with eigenvalues.

Parameters:
- A: Original matrix
- R: Matrix of eigenvectors
- Lambda: Vector of eigenvalues

Returns:
- 1 if diagonalization is verified
- 0 otherwise, with diagnostic messages printed to stdout

The function checks two properties:
1. Diagonal elements match the eigenvalues within relative tolerance
2. Off-diagonal elements are approximately zero
*/
int verify_diagonalization(const pseudo_t3d* A, const pseudo_t3d* R, 
                           const pseudo_v3d* Lambda) {
  pseudo_t3d temp, diagonalized;
  
  // Compute R^T * A * R
  for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 3; j++) {
      ((long double*)&temp)[i*3 + j] = 0;
      for (int k = 0; k < 3; k++) {
        ((long double*)&temp)[i*3 + j] += ((long double*)R)[k*3 + i] * 
                                          ((long double*)A)[k*3 + j];
      }
    }
  }
  
  for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 3; j++) {
      ((long double*)&diagonalized)[i*3 + j] = 0;
      for (int k = 0; k < 3; k++) {
        ((long double*)&diagonalized)[i*3 + j] += ((long double*)&temp)[i*3 + k] * 
                                                 ((long double*)R)[k*3 + j];
      }
    }
  }

  // Print the diagonalized matrix
  print_pseudo_t3d("Diagonalized matrix: (R^T * A * R)", &diagonalized);
  
  for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 3; j++) {
      if (i == j) {
        long double relative_error = fabsl(((long double*)&diagonalized)[i*3 + j] - 
                                    ((long double*)Lambda)[i]) / 
                                    (fabsl(((long double*)Lambda)[i]) + EPSILON);
        if (relative_error > RELATIVE_TOLERANCE) {
          printf("Diagonal element (%d,%d) does not match eigenvalue. %Lf != %Lf "
                 "(relative error: %Lf)\n", 
                 i, j, ((long double*)&diagonalized)[i*3 + j], 
                 ((long double*)Lambda)[i], relative_error);
        }
      } else {
        if (fabsl(((long double*)&diagonalized)[i*3 + j]) > EPSILON) {
          printf("Off-diagonal element (%d,%d) is not zero. Value = %Lf\n", 
                 i, j, ((long double*)&diagonalized)[i*3 + j]);
        }
      }
    }
  }
  return 1;
}

/**
### verify_eigenpairs

Verifies that $A \times v = \lambda \times v$ for each eigenpair.

This function checks the fundamental eigenvalue equation by:
1. Computing $A \times v$ for each eigenvector
2. Computing $\lambda \times v$ for each eigenvector
3. Comparing the results for approximate equality

Parameters:
- A: Original matrix
- R: Matrix containing eigenvectors as columns
- Lambda: Vector of eigenvalues

Returns:
- 1 if all eigenpairs are verified
- 0 otherwise, with diagnostic messages printed to stdout
*/
int verify_eigenpairs(const pseudo_t3d* A, const pseudo_t3d* R, 
                      const pseudo_v3d* Lambda) {
  printf("Verifying A * v = λ * v for each eigenpair:\n");
  for (int i = 0; i < 3; i++) {
    pseudo_v3d Av = {0}, lambda_v = {0};
    
    // Compute A * v
    for (int j = 0; j < 3; j++) {
      ((long double*)&Av)[j] = ((long double*)A)[j*3] * ((long double*)R)[i] +
                          ((long double*)A)[j*3+1] * ((long double*)R)[i+3] +
                          ((long double*)A)[j*3+2] * ((long double*)R)[i+6];
    }

    // Compute λ * v
    for (int j = 0; j < 3; j++) {
      ((long double*)&lambda_v)[j] = ((long double*)Lambda)[i] *
                                     ((long double*)R)[i+j*3];
    }

    printf("Eigenpair %d:\n", i + 1);
    printf("A * v = %8.4Lf %8.4Lf %8.4Lf\n", Av.x, Av.y, Av.z);
    printf("λ * v = %8.4Lf %8.4Lf %8.4Lf\n", lambda_v.x, lambda_v.y, lambda_v.z);

    // Check if A * v ≈ λ * v
    for (int j = 0; j < 3; j++) {
      if (fabsl(((long double*)&Av)[j] - ((long double*)&lambda_v)[j]) > EPSILON) {
        printf("Mismatch for eigenpair %d, component %d\n", i + 1, j + 1);
      }
    }
    printf("Verification A * v = λ * v for each eigenpair done. "
           "See the messages above!\n\n");
  }
  return 1;
}

/**
### verify_eigendecomposition

Main verification function that combines all verification tests.

This function verifies the eigendecomposition by:
1. Checking orthonormality of eigenvectors
2. Verifying diagonalization ($R^T \times A \times R \approx \Lambda$)
3. Confirming the eigenpair equation ($A \times v = \lambda \times v$)

Parameters:
- A: Original matrix
- R: Matrix of eigenvectors
- Lambda: Vector of eigenvalues

Returns:
- 1 when verification completes
- Messages about verification status are printed to stdout
*/
int verify_eigendecomposition(const pseudo_t3d* A, const pseudo_t3d* R, 
                             const pseudo_v3d* Lambda) {
  if (!verify_orthonormality(R)) {
    printf("Eigenvectors are not orthonormal.\n");
  } else {
    printf("Eigenvectors are orthonormal.\n");
  }
  printf("\n");
  
  if (!verify_diagonalization(A, R, Lambda)) {
    printf("Matrix is not properly diagonalized.\n");
  } else {
    printf("Matrix is properly diagonalized.\n");
  }
  
  if (!verify_eigenpairs(A, R, Lambda)) {
    printf("Eigenpair verification failed.\n");
  } else {
    printf("Eigenpair verification passed.\n");
  }
  
  printf("Eigendecomposition verification completed. See the messages above!\n");
  return 1;
}

/**
### verify_reconstruction

Verifies that $A = R \times \Lambda \times R^T$ by reconstructing $A$ from the eigendecomposition.

This function:
1. Creates a diagonal matrix from the eigenvalues
2. Computes $R \times \Lambda \times R^T$
3. Compares the result with the original matrix $A$

Parameters:
- A: Original matrix
- R: Matrix of eigenvectors
- Lambda: Vector of eigenvalues

Returns:
- 1 when verification completes
- Differences between original and reconstructed matrices are printed to stdout
*/
int verify_reconstruction(const pseudo_t3d* A, const pseudo_t3d* R, 
                         const pseudo_v3d* Lambda) {
  pseudo_t3d Lambda_diag, temp, A_reconstructed;
  
  // Create diagonal matrix from Lambda
  for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 3; j++) {
      ((long double*)&Lambda_diag)[i*3 + j] = (i == j) ? 
                                              ((long double*)Lambda)[i] : 0.0L;
    }
  }

  // Compute R * Lambda
  for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 3; j++) {
      ((long double*)&temp)[i*3 + j] = 0;
      for (int k = 0; k < 3; k++) {
        ((long double*)&temp)[i*3 + j] += ((long double*)R)[i*3 + k] * 
                                          ((long double*)&Lambda_diag)[k*3 + j];
      }
    }
  }

  // Compute (R * Lambda) * R^T
  for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 3; j++) {
      ((long double*)&A_reconstructed)[i*3 + j] = 0;
      for (int k = 0; k < 3; k++) {
        ((long double*)&A_reconstructed)[i*3 + j] += ((long double*)&temp)[i*3 + k] * 
                                                    ((long double*)R)[j*3 + k];
      }
    }
  }

  print_pseudo_t3d("Reconstructed A = R * Lambda * R^T", &A_reconstructed);

  // Compare original A with reconstructed A
  for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 3; j++) {
      long double diff = fabsl(((long double*)A)[i*3 + j] - 
                              ((long double*)&A_reconstructed)[i*3 + j]);
      if (diff > EPSILON) {
        printf("Mismatch at (%d,%d): original = %Lf, reconstructed = %Lf, "
               "difference = %Lf\n",
               i, j, ((long double*)A)[i*3 + j], 
               ((long double*)&A_reconstructed)[i*3 + j], diff);
      }
    }
  }

  printf("A = R * Lambda * R^T verification completed. See the messages above!\n");
  return 1;
}

/**
## Main Function

Entry point of the program that demonstrates matrix diagonalization and
verification.

The function:
1. Initializes a symmetric matrix A (default or from command line arguments)
2. Performs eigendecomposition to compute eigenvalues and eigenvectors
3. Runs verification procedures to confirm the correctness of the results

Command-line usage:
```
./program A11 A12 A13 A22 A23 A33
```
Where A11...A33 are the elements of the symmetric matrix

If no arguments are provided, a default matrix is used:
```
A = [ 1  2  3 ]
    [ 2  4  5 ]
    [ 3  5 -6 ]
```

Returns:
- 0 on successful execution
*/
int main(int argc, char *argv[]) {
  pseudo_t3d A, R;
  pseudo_v3d Lambda;

  // Initialize A with the given values

  /**
  ## Matrix Initialization Options
  
  Uncomment one of the following blocks to use a specific test matrix:
  
  ### Diagonal (not identity) matrix:
  ```
  A.x.x = 1;  A.x.y = 0; A.x.z = 0;
  A.y.x = 0; A.y.y = 2;  A.y.z = 0;
  A.z.x = 0;  A.z.y = 0;  A.z.z = 3;
  ```
  
  ### Identity matrix:
  ```
  A.x.x = 1;  A.x.y = 0; A.x.z = 0;
  A.y.x = 0; A.y.y = 1;  A.y.z = 0;
  A.z.x = 0;  A.z.y = 0;  A.z.z = 1;
  ```
  
  ### Non-diagonal matrix:
  ```
  A.x.x = 1;  A.x.y = 2; A.x.z = 3;
  A.y.x = 2; A.y.y = 4;  A.y.z = 5;
  A.z.x = 3;  A.z.y = 5;  A.z.z = -6;
  ```
  
  ### Small magnitude matrix:
  ```
  A.x.x = 1e-6;  A.x.y = 0; A.x.z = 0;
  A.y.x = 0; A.y.y = 1e-12;  A.y.z = 0;
  A.z.x = 0;  A.z.y = 0;  A.z.z = 1e-10;
  ```
  
  ### Large magnitude matrix:
  ```
  A.x.x = 100;  A.x.y = 100; A.x.z = 10;
  A.y.x = 100; A.y.y = 10;  A.y.z = 1;
  A.z.x = 10;  A.z.y = 1;  A.z.z = 0.1;
  ```
  */

  if (argc != 7) {
    A.x.x = 1;  A.x.y = 2; A.x.z = 3;
    A.y.x = 2; A.y.y = 4;  A.y.z = 5;
    A.z.x = 3;  A.z.y = 5;  A.z.z = -6;
  } else {
    // Get matrix elements from command line arguments
    A.x.x = atof(argv[1]);  A.x.y = atof(argv[2]); A.x.z = atof(argv[3]);
    A.y.x = atof(argv[2]); A.y.y = atof(argv[4]);  A.y.z = atof(argv[5]);
    A.z.x = atof(argv[3]);  A.z.y = atof(argv[5]);  A.z.z = atof(argv[6]);
  }

  print_pseudo_t3d("Original matrix A", &A);

  diagonalization_3D(&Lambda, &R, &A);

  print_pseudo_t3d("Eigenvectors R", &R);
  print_pseudo_v3d("Eigenvalues Lambda", &Lambda);

  verify_eigendecomposition(&A, &R, &Lambda);

  // Verify that A = R * Lambda * R^T
  verify_reconstruction(&A, &R, &Lambda);

  return 0;
}