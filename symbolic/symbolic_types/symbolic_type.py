#
# Copyright (c) 2011, EPFL (Ecole Politechnique Federale de Lausanne)
# All rights reserved.
#
# Created by Marco Canini, Daniele Venzano, Dejan Kostic, Jennifer Rexford
#
# Updated by Thomas Ball (2014)
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   -  Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#   -  Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#   -  Neither the names of the contributors, nor their associated universities or
#      organizations may be used to endorse or promote products derived from this
#      software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT
# SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import utils
import ast

# In Python, Booleans are a subclass of Integers, so we ensure this by wrapping comparisons
# in SymbolicInteger. This allows nonsense such as (x<y)+1, just as in C!

def wrap(o):
	from integers import SymbolicInteger # dodge circular reference
	return lambda l,r : SymbolicInteger("se",ast.BinOp(left=l, op=o(), right=r))

# the base class for representing any expression that depends on a symbolic input
# it also tracks the corresponding concrete value for the expression (aka concolic execution)

class SymbolicType:
	def __init__(self, name, expr=None):
		self.name = name
		self.concrete_value = None
		self.expr = expr

	# START - must override when creating subclass

	def getExprConcr(self):
		return (self.expr, self.getConcrValue())

	def isVariable(self):
		return self.expr == None

	# END - must override when creating subclass

	def getConcrValue(self):
		return self.concrete_value

	def setConcrValue(self, value):
		self.concrete_value = value

	def symbolicEq(self, other):
		if not isinstance(other,SymbolicType):
			return False;
		if self.isVariable() or other.isVariable():
			return self is other
		return self._do_symbolicEq(self.expr,other.expr)

	def _do_symbolicEq(self, expr1, expr2):
		if type(expr1) != type(expr2):
			return False
		if isinstance(expr1, ast.BinOp):
			ret = self._do_symbolicEq(expr1.left, expr2.left)
			ret |= self._do_symbolicEq(expr1.right, expr2.right)
			return ret | (type(expr1.op) == type(expr2.op))
		elif isinstance(expr1, SymbolicType):
			return expr1 is expr2
		elif isinstance(expr1, int) or isinstance(expr2, long):
			return expr1 == expr2
		else:
			utils.crash("Node type not supported")

	def getSymVariable(self):
		return self._getSymVariables(self.expr)

	def __nonzero__(self):
		return bool(self.getConcrValue())

	def __ord__(self):
		return self

	def __hash__(self):
		return hash(self.getConcrValue())

	def __cmp__(self, other):
		return NotImplemented

	def __repr__(self):
		return "SymExpr(" + ast.dump(self.expr) + ")"

	def __eq__(self, other):
		if isinstance(other, type(None)):
			return False
		else:
			return self._do_bin_op(other, lambda x, y: x == y, wrap(ast.Eq))

	def __ne__(self, other):
		if isinstance(other, type(None)):
			return True
		else:
			return self._do_bin_op(other, lambda x, y: x != y, wrap(ast.NotEq))

	def __lt__(self, other):
		return self._do_bin_op(other, lambda x, y: x < y, wrap(ast.Lt))

	def __le__(self, other):
		return self._do_bin_op(other, lambda x, y: x <= y, wrap(ast.LtE))

	def __gt__(self, other):
		return self._do_bin_op(other, lambda x, y: x > y, wrap(ast.Gt))

	def __ge__(self, other):
		return self._do_bin_op(other, lambda x, y: x >= y, wrap(ast.GtE))

	# compute both the symbolic and concrete image of operator
	def _do_bin_op(self, other, fun, wrap):
		left_expr, left_concr = self.getExprConcr()
		if isinstance(other, int) or isinstance(other, long):
			right_expr = other
			right_concr = other
		elif isinstance(other, SymbolicType):
			right_expr, right_concr = other.getExprConcr()
		else:
			return NotImplemented
		ret = wrap(left_expr,right_expr)
		ret.concrete_value = fun(left_concr, right_concr)
		# DEBUG
		print ret
		print ret.concrete_value
		return ret

	def __getstate__(self):
		filtered_dict = {}
		filtered_dict["concrete_value"] = self.concrete_value
		return filtered_dict

	def _getSymVariables(self, expr):
		sym_vars = []
		if isinstance(expr, ast.BinOp):
			sym_vars += self._getSymVariables(expr.left)
			sym_vars += self._getSymVariables(expr.right)
		elif isinstance(expr, SymbolicType):
			sym_vars += expr.getSymVariable()
		elif isinstance(expr, int) or isinstance(expr, long):
			pass
		else:
			utils.crash("Node type not supported: %s" % expr)
		return sym_vars

