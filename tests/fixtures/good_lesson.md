# Introduction to RAG (Retrieval-Augmented Generation)

## What you will learn

In this lesson, you will learn one important idea in AI. It is called RAG. By the end, you will know three things. You will know what RAG is. You will know why people use it. You will know how it works, step by step.

You do not need any coding or maths for this lesson. You only need to read slowly. Let us start.

## Why does this matter?

You have probably used ChatGPT. ChatGPT is an LLM. LLM means "large language model". It is a computer program that learned from a very large amount of text. Because of this, it can answer questions and write text like a person.

But an LLM has some problems.

First, it learned from text only up to a certain date. So it does not know about new things. Second, it never saw your private papers. It has not read your college notice board or your company's rules. Third, sometimes it does not know an answer, but it still gives one. The answer sounds sure, but it is wrong. This is called hallucination. Hallucination means the AI makes up an answer that is not true.

Think about an exam. A student who did not study may still write something. It may sound good. But it may be wrong. An LLM can do the same thing.

So we need a way to give the LLM the right information at the right time. That way is RAG.

## What is RAG?

Think about an open-book exam. In an open-book exam, you can look at your textbook. You do not need to remember everything. You find the right page. You read it. Then you write your answer from that page.

RAG works like an open-book exam for an LLM.

RAG stands for Retrieval-Augmented Generation. Let us look at each word.

- **Retrieval** means finding. The system finds useful information from a collection of documents. This collection is called the knowledge source. It can be PDFs, web pages, or notes.
- **Augmented** means "added to". The system adds the found information to your question. Your question plus the found information together are called the prompt. A prompt is the text we send to the LLM.
- **Generation** means writing. The LLM writes the answer using that information.

So, in simple words, RAG means: first find the right information, then add it to the question, then let the LLM write the answer.

The search step is done by a separate part of the system. It is not done by the LLM itself.

## How does it work?

RAG has two stages. The first stage is preparation. It happens once, before anyone asks a question. The second stage happens every time someone asks a question.

**Stage 1: Preparation**

1. **Split the documents.** Long documents are cut into small pieces. Each piece is called a chunk. A chunk may be a short paragraph. Small chunks are easier to search.
2. **Turn each chunk into numbers.** A computer cannot understand meaning the way we do. So each chunk is changed into a list of numbers. This list is called an embedding. An embedding is a list of numbers that shows the meaning of the text. Texts with similar meaning get similar numbers. This is true even when they use different words. A list of numbers like this is also called a vector.
3. **Store the embeddings.** All the embeddings are saved in a special store. It is called a vector database. A vector database is a store that can quickly find embeddings that are close to each other.

**Stage 2: Answering a question**

1. **Turn the question into numbers.** Your question is also changed into an embedding.
2. **Find the closest chunks.** The system compares your question's embedding with the stored embeddings. It picks the few chunks with the closest meaning. This is called similarity search. Similarity search means finding the texts whose meaning is most like your question.
3. **Add the chunks to the prompt.** The system puts the top chunks and your question together in one prompt.
4. **Write the answer.** The LLM reads the prompt. It writes the answer using the chunks.

Remember the open-book exam. Stage 1 is like making a good index for your textbook. Stage 2 is like finding the right page and writing your answer from it.

## A full example, step by step

Imagine Priya is a student at a college in Pune. The college has put all its rules and notices into a RAG chatbot.

1. **The documents.** The college documents are split into chunks. Here are three chunks:

> Chunk A: "The college library is open from 9 am to 8 pm, Monday to Saturday."
> Chunk B: "Students can borrow up to 4 books for 14 days."
> Chunk C: "The canteen serves lunch from 12 pm to 3 pm."

2. **The question.** Priya asks:

> "How many books can I take from the library, and for how long?"

3. **Retrieval.** The system turns her question into an embedding. It finds that Chunk B is closest in meaning. Chunk A is also about the library, so it comes second. Chunk C is about food, so it is not picked.

4. **The prompt.** The system sends this text to the LLM:

> "Use the information below to answer the question. Information: Students can borrow up to 4 books for 14 days. The college library is open from 9 am to 8 pm, Monday to Saturday. Question: How many books can I take from the library, and for how long?"

5. **The answer.** The LLM replies:

> "You can borrow up to 4 books at a time, for 14 days. The library is open from 9 am to 8 pm, Monday to Saturday."

The LLM never saw these college rules during its training. It could answer only because RAG gave it the right chunks.

## Where can it go wrong?

RAG is very useful. But it is not perfect.

- **Wrong chunks.** If the search finds the wrong chunks, the answer can be wrong.
- **Missing information.** If the answer is not in the documents, RAG cannot find it. The LLM may still guess.
- **Bad chunk size.** If chunks are too big, they waste space. An LLM can read only a limited amount of text at one time. If chunks are too small, they lose their meaning.

So RAG reduces hallucination. It does not remove it completely. A good system can show the sources it used, so a person can check the answer.

Also note one more thing. RAG does not change the LLM. The LLM is not trained again. It does not keep the information after it answers. For the next question, the system searches again.

## Key takeaways

- An LLM does not know new or private information, and it can make up answers.
- RAG means Retrieval-Augmented Generation: find information, add it to the question, then write the answer.
- In preparation, documents are cut into chunks, turned into embeddings, and saved in a vector database.
- For each question, the system finds the closest chunks and adds them to the prompt.
- RAG is used in help chatbots for companies, in tools that answer from office or college documents, and in study helpers that answer from your own notes.
- To update what the system knows, you only update the documents.
- RAG reduces mistakes, but the answer is only as good as the chunks it finds.

## Glossary

- **LLM (large language model)**: a computer program that learned from a lot of text and can write answers.
- **Hallucination**: when an AI gives an answer that sounds sure but is not true.
- **RAG**: Retrieval-Augmented Generation, a way to give an LLM the right information before it answers.
- **Retrieval**: finding useful information.
- **Augmented**: added to.
- **Generation**: writing the answer.
- **Knowledge source**: the collection of documents the system searches.
- **Prompt**: the text we send to the LLM.
- **Chunk**: a small piece of a document.
- **Embedding**: a list of numbers that shows the meaning of a text.
- **Vector**: a list of numbers.
- **Vector database**: a store that saves embeddings and finds similar ones quickly.
- **Similarity search**: finding texts whose meaning is closest to the question.
- **Index**: a list that helps you find things quickly, like the index at the back of a book.

## Check your understanding

**Q1.** Why can an LLM give a wrong answer about your college rules?
**Answer:** Because it never saw your college rules during training, so it may guess.

**Q2.** What do the three words in RAG mean?
**Answer:** Retrieval means finding information, Augmented means adding it to the question, and Generation means writing the answer.

**Q3.** What is an embedding?
**Answer:** A list of numbers that shows the meaning of a piece of text.

**Q4.** Does RAG retrain the LLM?
**Answer:** No. RAG only gives the LLM information inside the prompt. The LLM itself does not change.
