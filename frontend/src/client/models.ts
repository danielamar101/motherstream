export type Body_login_login_access_token = {
  grant_type?: string | null
  username: string
  password: string
  scope?: string
  client_id?: string | null
  client_secret?: string | null
}

export type HTTPValidationError = {
  detail?: Array<ValidationError>
}

export type ItemCreate = {
  title: string
  description?: string | null
}

export type ItemPublic = {
  title: string
  description?: string | null
  id: string
  owner_id: string
}

export type ItemUpdate = {
  title?: string | null
  description?: string | null
}

export type ItemsPublic = {
  data: Array<ItemPublic>
  count: number
}

export type Message = {
  message: string
}

export type NewPassword = {
  token: string
  new_password: string
}

export type Token = {
  access_token: string
  token_type?: string
}

export type UpdatePassword = {
  current_password: string
  new_password: string
}

export type UserCreate = {
  email: string
  dj_name: string
  timezone: string
  profile_picture?: string | null
  is_active?: boolean
  is_superuser?: boolean
  password: string
}

export type UserPublic = {
  email: string
  dj_name: string 
  stream_key: string
  timezone: string
  profile_picture?: string | null
  is_active?: boolean
  is_superuser?: boolean
  id: string
}

export type UserRegister = {
  email: string
  password: string
  dj_name: string 
  timezone: string
  profile_picture?: string | null
}

export type UserUpdate = {
  email?: string | null
  is_active?: boolean
  is_superuser?: boolean
  password?: string | null
  dj_name?: string 
  timezone?: string
  profile_picture?: string | null
}

export type UserUpdateMe = {
  email?: string | null
  stream_key?: string | null
  dj_name?: string | null
  timezone?: string | null
  profile_picture?: string | null
}

export type UsersPublic = {
  data: Array<UserPublic>
  count: number
}

export type ValidationError = {
  loc: Array<string | number>
  msg: string
  type: string
}
