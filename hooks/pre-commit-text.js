#!/usr/bin/env node
/**
 * Writing Agent-Kit - Pre-Commit Text Validation Hook
 * 
 * This script runs locally before a final draft is "committed" or finalized.
 * In a real environment, this would spawn `textlint` or `prh` to check for:
 * - Forbidden words (AI clichés)
 * - Spellcheck
 * - Consistency (e.g., formatting of dates and names)
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

async function main() {
  const args = process.argv.slice(2);
  const targetFile = args[0];

  if (!targetFile || !fs.existsSync(targetFile)) {
    console.error('Usage: node pre-commit-text.js <path-to-markdown-file>');
    process.exit(1);
  }

  console.log(`\n🔍 Running Text Validation on: ${targetFile}...\n`);

  try {
    // Simulated textlint execution
    // In production: execSync(`npx textlint ${targetFile}`, { stdio: 'inherit' });
    
    const content = fs.readFileSync(targetFile, 'utf8');
    let errorsFound = 0;

    // Hardcoded simple checks for demonstration
    const bannedPhrases = ["In conclusion,", "Let's delve into", "It's important to note"];
    
    bannedPhrases.forEach(phrase => {
      if (content.includes(phrase)) {
        console.error(`🚨 ERROR: Found banned AI phrase: "${phrase}"`);
        errorsFound++;
      }
    });

    if (errorsFound > 0) {
      console.error(`\n❌ Text validation failed with ${errorsFound} errors. Please fix before finalizing.`);
      process.exit(1);
    } else {
      console.log('✅ Text validation passed! The draft is clean.');
      process.exit(0);
    }
  } catch (error) {
    console.error('Failed to run text validation process:', error.message);
    process.exit(1);
  }
}

main();
