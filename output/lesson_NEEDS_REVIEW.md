> ⚠️ **NOT SHIPPED - needs human review.** This is the best attempt but it still fails: key_points. See rejection_log.md.

# Introduction to RAG (Retrieval-Augmented Generation)

## What you will learn

You use apps like ChatGPT every day. An LLM, or large language model, is a smart computer program that reads and writes text. It learns from a big amount of text up to a certain date. 

It does not know your private documents or very new information. It can confidently make up wrong answers. This wrong answer problem is called hallucination. 

Think of this like an exam hall. You are the student taking the exam. Your mind is the LLM. You studied before the exam, but you do not know the exact questions of the test paper in advance. 

You will learn how to fix this problem using a method called RAG. You can use RAG for customer-support chatbots that answer from company help pages. You can also use it to ask questions over college documents or your own study notes.

## Why does this matter?

You want your AI assistant to read your personal notes without making mistakes. With RAG, the LLM can use private and up-to-date information. 

The best part is that you do not need to retrain the model. Retraining means changing the internal settings of the model to learn new facts. RAG keeps answers more grounded in real facts. 

This reduces hallucinations. The system can even show which sources it used for the answer. Updating your knowledge source is simple as updating your documents.

## What is RAG?

RAG stands for Retrieval-Augmented Generation. Before the LLM answers, a separate search step finds relevant information from a chosen knowledge source. The search step gives this information to the LLM together with your question. The LLM writes the final answer based on that information. 

Let us break down the name word by word. Retrieval means finding the useful information from your documents. Augmented means adding this found information to your question. Generation means the LLM writes the answer using the added information. 

The knowledge source can be PDFs, web pages, notes, or help-centre articles. Going back to our exam hall analogy, retrieval is the exact moment you open your textbook to the right page during the exam.

## How does it work?

RAG works in two main parts. First is the preparation step, which is done once before you ask any questions. Your documents are split into small pieces called chunks. 

Each chunk is turned into an embedding, which is a list of numbers that captures its meaning. The embeddings are stored in a vector database, which is a special system that stores embeddings and finds similar ones. 

Second is the question step, which happens every time you ask something. Your question is also turned into an embedding. The system does a similarity search to find the chunks whose meaning is closest to your question. 

The top few chunks are added to your prompt, which is the text instruction you give to the LLM. The LLM reads your question along with these chunks and writes the answer.

## A full example, step by step

Imagine Priya is studying for her college history exam. She has a PDF notes file about the Maratha empire and asks a question. Here is how RAG helps her step by step.

1. **Preparation:** You split your history PDF into small text chunks and save their embeddings in your vector database.
2. **User Question:** Priya asks a question.
> Question: Where was Shivaji Maharaj born?
3. **Retrieval:** The system turns her question into an embedding and searches the vector database for matching text.
> Retrieved Text: Snippet 1: Shivaji Maharaj was born at Shivneri fort in 1630.
4. **Prompt Building:** The system combines the question and the retrieved text into one prompt for the LLM.
> Prompt: Read this text: "Snippet 1: Shivaji Maharaj was born at Shivneri fort in 1630." Answer the question: Where was Shivaji Maharaj born?
5. **Generation:** The LLM reads the combined prompt and writes the final answer.
> Answer: Shivaji Maharaj was born at Shivneri fort in 1630.

## Where can it go wrong?

RAG is very helpful, but it has limits. The answer is only as good as what the search finds. If the search finds wrong or unrelated chunks, the answer can be wrong. 

If the right information is not in your documents at all, the model may still guess. RAG reduces hallucinations, but it does not remove them completely.

## Key takeaways

LLMs can hallucinate and do not know your private documents. RAG fixes this by searching documents first and giving that text to the LLM. 

Retrieval means finding, augmented means adding, and generation means writing. RAG lets you use private data without retraining the model. The quality of the answer depends entirely on the quality of the retrieved text.

## Glossary

- **LLM**: A large language model, like ChatGPT, that reads and writes text.
- **Hallucination**: When an AI model confidently makes up a wrong answer.
- **RAG**: Retrieval-Augmented Generation, a method that gives relevant document text to the LLM before it answers.
- **Retrieval**: The step of finding useful information from a knowledge source.
- **Augmented**: The step of adding retrieved text to the prompt.
- **Generation**: The step where the LLM writes the final answer.
- **Chunk**: A small piece of a document.
- **Embedding**: A list of numbers that captures the meaning of a text.
- **Vector database**: A special system that stores embeddings and finds similar ones.
- **Similarity search**: The process of finding text chunks whose meaning is closest to a question.
- **Prompt**: The text instruction and data given to the LLM.
- **Retraining**: Changing the internal settings of an AI model to teach it new facts.

## Check your understanding

**Q1.** What does RAG stand for?
**Answer:** Retrieval-Augmented Generation.

**Q2.** What is a hallucination in AI?
**Answer:** When an AI model confidently makes up a wrong answer.

**Q3.** What is an embedding?
**Answer:** A list of numbers that captures the meaning of a text.

**Q4.** Does RAG completely remove hallucinations?
**Answer:** No, it reduces them, but does not remove them completely.
