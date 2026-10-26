const test = require("node:test");
const assert = require("node:assert");
const { add, multiply } = require("./calc.js");

test("adds two numbers", () => {
  assert.strictEqual(add(2, 3), 5);
});

test("multiplies numbers", () => {
  assert.strictEqual(multiply(4, 5), 20);
});
