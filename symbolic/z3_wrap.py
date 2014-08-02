# Copyright: see copyright.txt

import sys
import ast
import logging
import utils
from z3 import *
from .symbolic_types.symbolic_int import SymbolicInteger
from .symbolic_types.symbolic_type import SymbolicType

class Z3Wrapper(object):
	def __init__(self):
		self.log = logging.getLogger("se.z3")
		self.solver = Solver()
		self.z3_vars = {}
		self.N = 32
		self.asserts = None
		self.query = None

	def findCounterexample(self, asserts, query):
		"""Tries to find a counterexample to the query while
	  	 asserts remains valid."""
		self.asserts = asserts
		self.query = query
		return self._findModel()

	# private

	def _getModel(self):
		res = {}
		model = self.solver.model()
		#print("Model is ")
		#print(model)
		for name in self.z3_vars.keys():
			try:
				ce = model.eval(self.z3_vars[name])
				res[name] = ce.as_signed_long()
			except:
				pass
		return res
	
	# turn the validity query (assertions => query) into satisfiability in Z3
	def _generateZ3(self):
		self.z3_vars = {}
		self.solver.assert_exprs([self._to_Z3(p) for p in self.asserts])
		self.solver.assert_exprs(Not(self._to_Z3(self.query)))

	def _to_Z3(self,pred,env=None):
		sym_expr = self._astToZ3Expr(pred.expr,env)
		if env == None:
			if not is_bool(sym_expr):
				sym_expr = sym_expr != self._int2BitVec(0)
			if not pred.result:
				sym_expr = Not(sym_expr)
		else:
			if not pred.result:
				sym_expr = not sym_expr
		return sym_expr

	def _findModel(self):
		self.N = 32
		while self.N <= 128:
			self.solver.push()
			(ret,mismatch) = self._findModel2()
			if (not mismatch):
				break
			self.solver.pop()
			self.N = self.N+8
			print("expanded bit width to "+str(self.N))
		#print("Assertions")
		#print(self.solver.assertions())
		if ret == unsat:
			self.log.warning("Z3: UNSAT")
			self.solver.pop()
			return None
		elif ret == unknown:
			self.log.error("Z3: UNKNOWN")
			self.solver.pop()
			return None
		res = self._getModel()
		self.solver.pop()
		return res

	def _findModel2(self):
		self._generateZ3()
		int_vars = self._getIntVars()
		res = unsat
		bound = (1 << 4) - 1
		while res == unsat and bound < (1 << self.N):
			self.solver.push()
			constraints = self._boundIntegers(int_vars,bound)
			self.solver.assert_exprs(constraints)
			res = self.solver.check()
			if res == unsat:
				bound = (bound << 1)+1
				self.solver.pop()
		if res == sat:
			# Does concolic agree with Z3? If not, it may be due to overflow
			model = self._getModel()
			self.solver.pop()
			mismatch = False
			for a in self.asserts:
				eval = self._to_Z3(a,model)
				if (not eval):
					mismatch = True
					break
			if (not mismatch):
				mismatch = not (not self._to_Z3(self.query,model))
			return (res,mismatch)
		return (res,False)

	def _getIntVars(self):
		int_vars = []
		for v in self.z3_vars.items():
			if isinstance(v[1],BitVecRef):
				int_vars.append(v[1]) 
		return int_vars

	def _boundIntegers(self,vars,val):
		bval = BitVecVal(val,self.N,self.solver.ctx)
		bval_neg = BitVecVal(-val+1,self.N,self.solver.ctx)
		return And([ v <= bval for v in vars]+[ bval_neg < v for v in vars])

	def _getIntegerVariable(self,name):
		if name not in self.z3_vars:
			self.z3_vars[name] = BitVec(name,self.N, self.solver.ctx)
		else:
			self.log.error("Trying to create a duplicate variable")
		return self.z3_vars[name]

	def _int2BitVec(self,v):
		return BitVecVal(v, self.N, self.solver.ctx)

	def _wrapIf(self,e,env):
		if env == None:
			return If(e,self._int2BitVec(1),self._int2BitVec(0))
		else:
			return e

	# add concrete evaluation to this, to check
	def _astToZ3Expr(self,expr,env=None):
		if isinstance(expr, ast.BinOp):
			z3_l = self._astToZ3Expr(expr.left,env)
			z3_r = self._astToZ3Expr(expr.right,env)

			# arithmetical operations
			if isinstance(expr.op, ast.Add):
				return z3_l + z3_r
			elif isinstance(expr.op, ast.Sub):
				return z3_l - z3_r
			elif isinstance(expr.op, ast.Mult):
				return z3_l * z3_r
			elif isinstance(expr.op, ast.Div):
				return z3_l / z3_r
			elif isinstance(expr.op, ast.Mod):
				return z3_l % z3_r

			# bitwise
			elif isinstance(expr.op, ast.LShift):
				return z3_l << z3_r
			elif isinstance(expr.op, ast.RShift):
				return z3_l >> z3_r
			elif isinstance(expr.op, ast.BitXor):
				return z3_l ^ z3_r
			elif isinstance(expr.op, ast.BitOr):
				return z3_l | z3_r
			elif isinstance(expr.op, ast.BitAnd):
				return z3_l & z3_r

			# equality gets coerced to integer
			elif isinstance(expr.op, ast.Eq):
				return self._wrapIf(z3_l == z3_r,env)
			elif isinstance(expr.op, ast.NotEq):
				return self._wrapIf(z3_l != z3_r,env)
			elif isinstance(expr.op, ast.Lt):
				return self._wrapIf(z3_l < z3_r,env)
			elif isinstance(expr.op, ast.Gt):
				return self._wrapIf(z3_l > z3_r,env)
			elif isinstance(expr.op, ast.LtE):
				return self._wrapIf(z3_l <= z3_r,env)
			elif isinstance(expr.op, ast.GtE):
				return self._wrapIf(z3_l >= z3_r,env)

			else:
				utils.crash("Unknown BinOp during conversion from ast to Z3 (expressions): %s" % expr.op)

		elif isinstance(expr, SymbolicInteger):
			if expr.isVariable():
				if env == None:
					return self._getIntegerVariable(expr.name)
				else:
					return env[expr.name]
			else:
				return self._astToZ3Expr(expr.expr,env)

		elif isinstance(expr, SymbolicType):
			return self._astToZ3Expr(expr.expr,env)

		elif isinstance(expr, int) or isinstance(expr, long):
			if env == None:
				return self._int2BitVec(expr)
			else:
				return expr
		else:
			utils.crash("Unknown node during conversion from ast to Z3 (expressions): %s" % expr)

