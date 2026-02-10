---
name: mikro-orm
description: "Use when working with MikroORM — entity design, repositories, migrations, query patterns, unit of work, and best practices for TypeScript database layers."
---

# MikroORM Best Practices

## Overview

Guide for building database layers with MikroORM. Covers entity design, relationships, migrations, querying, unit of work patterns, and common pitfalls.

## Entity Design

**Always use the `@Entity` decorator with explicit table names:**

```typescript
@Entity({ tableName: 'users' })
export class User {
  @PrimaryKey()
  id!: number;

  @Property()
  name!: string;

  @Property({ unique: true })
  email!: string;

  @Property()
  createdAt: Date = new Date();

  @Property({ onUpdate: () => new Date() })
  updatedAt: Date = new Date();
}
```

**Prefer `defineConfig` for configuration:**

```typescript
export default defineConfig({
  entities: ['./dist/entities'],
  entitiesTs: ['./src/entities'],
  dbName: 'mydb',
  type: 'postgresql',
});
```

## Relationships

**Use `Rel<>` wrapper for circular reference handling:**

```typescript
@Entity()
export class Author {
  @OneToMany(() => Book, book => book.author)
  books = new Collection<Book>(this);
}

@Entity()
export class Book {
  @ManyToOne(() => Author)
  author!: Rel<Author>;
}
```

**Relationship loading — prefer explicit population:**

```typescript
// Good: explicit about what you load
const author = await em.findOne(Author, id, {
  populate: ['books', 'books.tags'],
});

// Avoid: lazy loading causes N+1
const books = await author.books.loadItems();
```

## Unit of Work

**Let the UoW batch operations — don't flush after every change:**

```typescript
// Good
const user = em.create(User, { name: 'Alice', email: 'alice@example.com' });
const profile = em.create(Profile, { user, bio: 'Hello' });
await em.flush(); // Single transaction, both inserts

// Bad: flushing per operation
em.persist(user);
await em.flush();
em.persist(profile);
await em.flush();
```

## Query Builder

**Use `qb` for complex queries, `em.find` for simple ones:**

```typescript
// Simple: use em.find
const users = await em.find(User, { role: 'admin' }, {
  orderBy: { createdAt: QueryOrder.DESC },
  limit: 10,
});

// Complex: use QueryBuilder
const qb = em.createQueryBuilder(User, 'u');
const results = await qb
  .select(['u.*', raw('count(b.id) as book_count')])
  .leftJoin('u.books', 'b')
  .groupBy('u.id')
  .having({ book_count: { $gt: 5 } })
  .execute();
```

## Migrations

**Always generate migrations from entity changes, never write them manually:**

```bash
# Generate migration from entity diff
npx mikro-orm migration:create

# Run pending migrations
npx mikro-orm migration:up

# Check migration status
npx mikro-orm migration:pending
```

**Name migrations descriptively when prompted.**

## Filters

**Use global filters for soft-delete and multi-tenancy:**

```typescript
@Filter({
  name: 'notDeleted',
  cond: { deletedAt: null },
  default: true,
})
@Entity()
export class Post {
  @Property({ nullable: true })
  deletedAt?: Date;
}
```

## Testing

**Use `MikroORM.init` with SQLite for unit tests:**

```typescript
let orm: MikroORM;

beforeAll(async () => {
  orm = await MikroORM.init({
    entities: [User, Post],
    dbName: ':memory:',
    type: 'sqlite',
  });
  await orm.schema.createSchema();
});

afterEach(async () => {
  await orm.em.nativeDelete(User, {});
  orm.em.clear();
});

afterAll(() => orm.close(true));
```

## Common Pitfalls

- **Don't reuse `EntityManager` across requests** — always fork: `const em = orm.em.fork();`
- **Don't forget `persist`** — `em.create()` auto-persists, but manual instantiation does not
- **Don't mix `em.find` results across forks** — entities are bound to their identity map
- **Wrap request handlers** with `RequestContext.create(orm.em)` or use the middleware
- **Always run `em.flush()`** — changes aren't saved until you flush
